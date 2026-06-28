"""Shared helpers for the Solcore Quasi-3D <-> 2L-FEST cross-validation.

KEY LESSON (debugged 2026-06): the high-level solve_quasi_3D() first runs
solar_cell_solver(cell,'iv'), which for a kind='2D' junction is "ignored in
optics" and OVERWRITES junction.jsc to 0 -> no photocurrent. So we bypass it
and drive the low-level solve_circuit_quasi3D() directly with arrays we build
ourselves, in SI units. This also gives full control for a fair comparison.

Solcore solve_circuit_quasi3D unit convention (from reading the source):
  Isc, I01, I02 : A/m^2      (per-area current densities)
  Rshunt        : Ohm*m^2
  Rseries       : Ohm*m^2    (series to back contact / next junction)
  RsTop, RsBot  : Ohm/sq     (lateral sheet resistance, top/bottom plane)
  Rline         : Ohm/sq     (metal sheet R = resistivity / finger height)
  Rcontact      : Ohm*m^2    (metal-semiconductor contact resistivity)
  Lx, Ly        : m          (pixel size)
  injection/contacts : 0-255 image masks
                       illumination = injection/255 ; contacts>200 = bus
                       (external terminal) ; contacts>55 = metal (shaded)
"""
import os
os.environ.setdefault("SOLCORE_SPICE", "/opt/homebrew/bin/ngspice")
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import solcore.spice.quasi_3D_solver as _q3d
from solcore.spice.quasi_3D_solver import solve_circuit_quasi3D

CM2_PER_M2 = 1e4
q = 1.602e-19; kB = 1.381e-23; T_DEFAULT = 298.15
VT_DEFAULT = kB * T_DEFAULT / q
_T_CELSIUS = 25.0   # match 2L-FEST T=298.15 K; Solcore hardcodes 20 C otherwise


def _create_header_25C(I01, I02, n1, n2, Eg, T=_T_CELSIUS):
    """Replacement for Solcore's create_header that sets TNOM=TEMP=25 C so the
    diode saturation currents we pass are used as-is at 2L-FEST's temperature
    (the stock version hardcodes TNOM=20, biasing Voc by ~2%)."""
    title = "*** A SPICE simulation with python (xval, 25 C)\n\n"
    diodes = ""
    for j in range(len(I01)):
        diodes += ".model diode1_{0} d(is={1},n={2},eg={3})\n".format(j, I01[j], n1[j], Eg[j])
        diodes += ".model diode2_{0} d(is={1},n={2},eg={3})\n".format(j, I02[j], n2[j], Eg[j])
    # convergence aids for large (fine-grid) diode networks: gmin stepping +
    # relaxed-but-safe tolerances + high DC iteration limits. Without these,
    # >~10k-node DC sweeps fail to converge -> empty output -> J=0.
    options = (".OPTIONS TNOM={0} TEMP={0} "
               "gmin=1e-12 gminsteps=10 reltol=1e-3 abstol=1e-10 vntol=1e-7 "
               "itl1=1000 itl2=500\n\n").format(T)
    independent_source = " \n    vdep in 0 DC 0\n    "
    return title + diodes + options + independent_source


# install the temperature-aligned header for all run_quasi3d() calls
_q3d.create_header = _create_header_25C


def run_quasi3d(injection, contacts, *, jsc, j01, j02, n1, n2, Eg,
                Rshunt, RsTop, RsBot, Rline, Rcontact, Rseries=1e-16,
                Lx=10e-6, Ly=10e-6, vini=0.0, vfin=0.78, step=0.005):
    """Drive Solcore's low-level quasi-3D SPICE solver for a SINGLE junction.

    All electrical inputs are in 2L-FEST native cm units; converted to SI here.
        jsc, j01, j02 : A/cm^2
        Rshunt, Rcontact, Rseries : Ohm*cm^2
        RsTop, RsBot, Rline : Ohm/sq
    Returns (V [V], J [A/cm^2]) with generation positive at short circuit.
    """
    Isc_a = np.array([jsc * CM2_PER_M2])
    I01_a = np.array([j01 * CM2_PER_M2])
    I02_a = np.array([max(j02, 1e-30) * CM2_PER_M2])
    n1_a = np.array([n1]); n2_a = np.array([n2]); Eg_a = np.array([Eg])
    Rsh_a = np.array([Rshunt / CM2_PER_M2])
    Rser_a = np.array([Rseries / CM2_PER_M2])
    RsTop_a = np.array([max(RsTop, 1e-16)])
    RsBot_a = np.array([max(RsBot, 1e-16)])
    Rcontact_si = Rcontact / CM2_PER_M2

    V, I, Vall, Vmet = solve_circuit_quasi3D(
        vini, vfin, step, Isc_a, I01_a, I02_a, n1_a, n2_a, Eg_a,
        Rsh_a, Rser_a, injection, contacts,
        RsTop_a, RsBot_a, Rline, Rcontact_si, Lx, Ly)

    V = np.asarray(V, float); I = np.asarray(I, float)
    nx, ny = injection.shape
    area_cm2 = (nx * Lx) * (ny * Ly) * CM2_PER_M2
    J = I / area_cm2
    # sign: generation positive at short circuit (smallest |V|)
    if J[np.argmin(np.abs(V))] < 0:
        J = -J
    return V, J


def run_quasi3d_tandem(injection, contacts, *, top, bot, Rc_junction=0.0,
                       RsTop_front, RsBot_rear=1e-3, Rline, Rcontact,
                       Lx=10e-6, Ly=10e-6, vini=0.0, vfin=2.2, step=0.005):
    """2-junction (2T tandem) Solcore quasi-3D: junction 0 = top, 1 = bottom.

    Front metal grid sits on junction 0 (top) only; rear contact on junction 1.
    The recombination junction between them is a vertical series resistance
    (Rc_junction, Ohm*cm^2) -> Phase-A representation, the only one Solcore's
    series-junction model supports (Phase-B lateral interlayer sheet has no DOF).

    `top`/`bot` are dicts with cm-unit keys: jsc, j01, j02, n1, n2, Eg, Rshunt.
    Returns (V [V], J [A/cm^2]) with generation positive at short circuit.
    """
    def col(k, scale):
        return np.array([top[k] * scale, bot[k] * scale])
    Isc = col("jsc", CM2_PER_M2)
    I01 = col("j01", CM2_PER_M2)
    I02 = np.array([max(top["j02"], 1e-30) * CM2_PER_M2, max(bot["j02"], 1e-30) * CM2_PER_M2])
    n1 = np.array([top["n1"], bot["n1"]]); n2 = np.array([top["n2"], bot["n2"]])
    Eg = np.array([top["Eg"], bot["Eg"]])
    Rsh = col("Rshunt", 1.0 / CM2_PER_M2)
    # series between junctions: [top->bot recomb junction, bot->back]. R_back small.
    Rseries = np.array([max(Rc_junction, 1e-16) / CM2_PER_M2, 1e-16])
    # lateral sheet: only the front TCO (top junction's top plane) is resistive;
    # interlayer & rear planes ~0 (vertical transport in Phase A).
    RsTop = np.array([max(RsTop_front, 1e-16), 1e-16])
    RsBot = np.array([1e-16, max(RsBot_rear, 1e-16)])

    V, I, Vall, Vmet = solve_circuit_quasi3D(
        vini, vfin, step, Isc, I01, I02, n1, n2, Eg, Rsh, Rseries,
        injection, contacts, RsTop, RsBot, Rline, Rcontact / CM2_PER_M2, Lx, Ly)

    V = np.asarray(V, float); I = np.asarray(I, float)
    nx, ny = injection.shape
    area_cm2 = (nx * Lx) * (ny * Ly) * CM2_PER_M2
    J = I / area_cm2
    if J[np.argmin(np.abs(V))] < 0:
        J = -J
    return V, J


def iv_metrics(V, J):
    """Metrics from a (V [V], J [A/cm^2]) generation curve (J>0 at V=0)."""
    V = np.asarray(V, float); J = np.asarray(J, float)
    o = np.argsort(V); V = V[o]; J = J[o]
    Jsc = float(np.interp(0.0, V, J))
    sign = np.sign(J)
    cr = np.where(np.diff(sign) < 0)[0]
    if len(cr):
        k = cr[0]
        Voc = V[k] - J[k] * (V[k + 1] - V[k]) / (J[k + 1] - J[k])
    else:
        Voc = float("nan")
    P = V * J
    m = (V >= 0) & (V <= (Voc if np.isfinite(Voc) else V.max()))
    Pmax = float(np.max(P[m])) if m.any() else float("nan")
    Vmpp = float(V[m][np.argmax(P[m])]) if m.any() else float("nan")
    FF = Pmax / (Voc * Jsc) if (np.isfinite(Voc) and Jsc) else float("nan")
    return dict(Jsc=Jsc, Voc=Voc, Pmax=Pmax, FF=FF, Vmpp=Vmpp)


def analytic_2diode(Varr, *, jsc, j01, j02, n1, n2, Rshunt, VT=VT_DEFAULT):
    """Closed-form illuminated 2-diode J(V) [A/cm^2], no series resistance."""
    return (jsc
            - j01 * (np.exp(Varr / (n1 * VT)) - 1.0)
            - j02 * (np.exp(Varr / (n2 * VT)) - 1.0)
            - Varr / Rshunt)
