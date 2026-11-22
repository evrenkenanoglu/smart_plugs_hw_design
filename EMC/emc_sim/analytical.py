"""Small SI-unit estimates for transmission lines and FDTD discretization.

These closed-form estimates are design aids, not measurements, certification
evidence, or substitutes for a validated numerical field solver.
"""

import math
from numbers import Integral, Real


_C0_M_PER_S = 299_792_458.0
_MU0_H_PER_M = 4e-7 * math.pi
_ETA0_OHM = 376.730313668


def _positive_finite(name: str, value: Real) -> float:
    """Return a finite positive real value, rejecting booleans and coercions."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite positive real number")
    try:
        converted = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite positive real number") from exc
    if not math.isfinite(converted) or converted <= 0.0:
        raise ValueError(f"{name} must be a finite positive real number")
    return converted


def _relative_permittivity(name: str, value: Real) -> float:
    relative_permittivity = _positive_finite(name, value)
    if relative_permittivity < 1.0:
        raise ValueError(f"{name} must be at least 1")
    return relative_permittivity


def _positive_integer(name: str, value: Integral) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _logaddexp(left: float, right: float) -> float:
    """Stable natural logarithm of exp(left) + exp(right)."""
    high = max(left, right)
    return high + math.log1p(math.exp(min(left, right) - high))


def _positive_from_log(name: str, logarithm: float) -> float:
    try:
        result = math.exp(logarithm)
    except OverflowError as exc:
        raise ValueError(f"{name} is outside the representable range") from exc
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} is outside the representable range")
    return result


def _microstrip_hj(width_m: Real, substrate_height_m: Real,
                   relative_permittivity: Real) -> tuple[float, float]:
    width = _positive_finite("width_m", width_m)
    height = _positive_finite("substrate_height_m", substrate_height_m)
    eps_r = _relative_permittivity("relative_permittivity", relative_permittivity)

    width_ratio = width / height
    if not math.isfinite(width_ratio) or width_ratio <= 0.0:
        raise ValueError("width_m / substrate_height_m must be representable")
    log_u = math.log(width_ratio)

    # Stable forms of Hammerstad-Jensen's finite-width correction terms.
    log_numerator = _logaddexp(4.0 * log_u, 2.0 * (log_u - math.log(52.0)))
    log_denominator = _logaddexp(4.0 * log_u, math.log(0.432))
    a = (
        1.0
        + (log_numerator - log_denominator) / 49.0
        + _logaddexp(0.0, 3.0 * (log_u - math.log(18.1))) / 18.7
    )
    b = 0.564 * ((eps_r - 0.9) / (eps_r + 3.0)) ** 0.053
    log_width_correction = _logaddexp(0.0, math.log(10.0) - log_u)
    try:
        eps_eff = (
            (eps_r + 1.0) / 2.0
            + (eps_r - 1.0) / 2.0
            * math.exp(-a * b * log_width_correction)
        )
    except OverflowError as exc:
        raise ValueError("microstrip dimensions are outside the model's range") from exc
    if not math.isfinite(eps_eff) or eps_eff <= 0.0:
        raise ValueError("microstrip dimensions are outside the model's range")

    log_exponent = 0.7528 * (math.log(30.666) - log_u)
    if log_exponent > math.log(float.fromhex("0x1.fffffffffffffp+1023")):
        exponential_correction = 0.0
    else:
        exponential_correction = math.exp(-math.exp(log_exponent))
    f_u = 6.0 + (2.0 * math.pi - 6.0) * exponential_correction

    log_sqrt_term = 0.5 * _logaddexp(
        0.0, 2.0 * (math.log(2.0) - log_u)
    )
    log_impedance_logarithm = _logaddexp(
        math.log(f_u) - log_u, log_sqrt_term
    )
    if log_impedance_logarithm <= 0.0:
        raise ValueError("microstrip dimensions are outside the model's range")
    log_z0 = (
        math.log(_ETA0_OHM / (2.0 * math.pi))
        + math.log(log_impedance_logarithm)
        - 0.5 * math.log(eps_eff)
    )
    z0 = _positive_from_log("characteristic impedance", log_z0)
    return z0, eps_eff


def microstrip_characteristic_impedance(
    width_m: Real,
    substrate_height_m: Real,
    relative_permittivity: Real,
) -> float:
    """Estimate zero-thickness microstrip characteristic impedance in ohms.

    Uses the quasi-static Hammerstad-Jensen equations for a rectangular strip
    over an effectively infinite ground plane and a homogeneous, isotropic
    dielectric (relative permittivity >= 1). Width and substrate height are
    positive metres. Conductor thickness, roughness, solder mask, dispersion,
    finite ground planes, and losses are omitted; extreme geometries may be
    outside the approximation's useful range.
    """
    return _microstrip_hj(width_m, substrate_height_m, relative_permittivity)[0]


def microstrip_effective_permittivity(
    width_m: Real,
    substrate_height_m: Real,
    relative_permittivity: Real,
) -> float:
    """Estimate zero-thickness microstrip effective relative permittivity.

    Uses the quasi-static Hammerstad-Jensen equations for a rectangular strip
    over an effectively infinite ground plane in a homogeneous, isotropic
    dielectric. Width and substrate height are positive metres; bulk relative
    permittivity must be >= 1. The model omits conductor thickness, roughness,
    solder mask, dispersion, and finite ground-plane effects.
    """
    return _microstrip_hj(width_m, substrate_height_m, relative_permittivity)[1]


def skin_depth(
    frequency_hz: Real,
    conductivity_s_per_m: Real,
    relative_permeability: Real = 1.0,
) -> float:
    """Return the good-conductor skin depth in metres.

    Assumes a homogeneous, isotropic conductor with positive conductivity and
    real positive relative permeability, under sinusoidal steady-state
    excitation. Uses delta = sqrt(1 / (pi * f * mu * sigma)); it neglects
    temperature dependence, material dispersion, and displacement current.
    Frequency and conductivity must be strictly positive, so DC is excluded.
    """
    frequency = _positive_finite("frequency_hz", frequency_hz)
    conductivity = _positive_finite("conductivity_s_per_m", conductivity_s_per_m)
    mu_r = _positive_finite("relative_permeability", relative_permeability)
    log_delta = -0.5 * (
        math.log(math.pi)
        + math.log(frequency)
        + math.log(_MU0_H_PER_M)
        + math.log(mu_r)
        + math.log(conductivity)
    )
    return _positive_from_log("skin depth", log_delta)


def wavelength_cell_limit(
    frequency_hz: Real,
    maximum_relative_permittivity: Real,
    points_per_wavelength: Integral = 10,
) -> float:
    """Return a wavelength-based maximum FDTD cell dimension in metres.

    Computes c / (f * sqrt(epsilon_r,max) * points_per_wavelength), using the
    vacuum speed of light and a nonmagnetic dielectric assumption. Frequency
    must be positive, maximum relative permittivity >= 1, and points per
    wavelength a positive integer. This is only a spatial-resolution heuristic;
    it does not ensure numerical accuracy or account for dispersion or geometry.
    """
    frequency = _positive_finite("frequency_hz", frequency_hz)
    eps_r_max = _relative_permittivity(
        "maximum_relative_permittivity", maximum_relative_permittivity
    )
    points = _positive_integer("points_per_wavelength", points_per_wavelength)
    log_limit = (
        math.log(_C0_M_PER_S)
        - math.log(frequency)
        - 0.5 * math.log(eps_r_max)
        - math.log(points)
    )
    return _positive_from_log("wavelength cell limit", log_limit)


def geometry_cell_spacing_limit(
    minimum_feature_m: Real,
    cells_per_feature: Integral = 3,
) -> float:
    """Return a geometric cell-spacing limit in metres.

    Divides a positive minimum feature dimension by the requested positive
    integer number of cells across it. This is a geometric meshing heuristic,
    not a solver-specific accuracy guarantee; identify the smallest feature
    that must be resolved before applying it.
    """
    feature = _positive_finite("minimum_feature_m", minimum_feature_m)
    cells = _positive_integer("cells_per_feature", cells_per_feature)
    return _positive_from_log(
        "geometry cell spacing", math.log(feature) - math.log(cells)
    )


def courant_timestep_limit(
    dx_m: Real,
    dy_m: Real,
    dz_m: Real,
    maximum_relative_permittivity: Real = 1.0,
    courant_factor: Real = 1.0,
) -> float:
    """Return the 3D Cartesian CFL timestep limit in seconds.

    Applies dt <= S / (c * sqrt(epsilon_r,max) *
    sqrt(1/dx**2 + 1/dy**2 + 1/dz**2)) to positive cell spacings in metres.
    The model assumes a nonmagnetic, homogeneous, nondispersive medium;
    maximum relative permittivity must be >= 1. ``courant_factor`` is a
    positive safety multiplier no greater than 1. This bound does not replace
    solver-specific stability guidance for dispersive, anisotropic, or
    non-Cartesian models.
    """
    dx = _positive_finite("dx_m", dx_m)
    dy = _positive_finite("dy_m", dy_m)
    dz = _positive_finite("dz_m", dz_m)
    eps_r_max = _relative_permittivity(
        "maximum_relative_permittivity", maximum_relative_permittivity
    )
    factor = _positive_finite("courant_factor", courant_factor)
    if factor > 1.0:
        raise ValueError("courant_factor must be no greater than 1")

    log_inverse_spacing_square_sum = _logaddexp(
        _logaddexp(-2.0 * math.log(dx), -2.0 * math.log(dy)),
        -2.0 * math.log(dz),
    )
    log_limit = (
        math.log(factor)
        - math.log(_C0_M_PER_S)
        - 0.5 * math.log(eps_r_max)
        - 0.5 * log_inverse_spacing_square_sum
    )
    return _positive_from_log("Courant timestep limit", log_limit)
