import math

import pytest

from emc_sim.analytical import (
    courant_timestep_limit,
    geometry_cell_spacing_limit,
    microstrip_characteristic_impedance,
    microstrip_effective_permittivity,
    skin_depth,
    wavelength_cell_limit,
)


def test_hammerstad_jensen_microstrip_reference_point():
    # A common PCB-scale geometry is close to a 50-ohm line.
    z0 = microstrip_characteristic_impedance(1.9e-3, 1.0e-3, 4.4)
    eps_eff = microstrip_effective_permittivity(1.9e-3, 1.0e-3, 4.4)

    assert z0 == pytest.approx(50.0, abs=1.0)
    assert eps_eff == pytest.approx(3.3292, rel=2e-4)
    assert 1.0 < eps_eff < 4.4


def test_microstrip_width_and_permittivity_trends():
    z_narrow = microstrip_characteristic_impedance(1.0e-3, 1.0e-3, 4.0)
    z_wide = microstrip_characteristic_impedance(2.0e-3, 1.0e-3, 4.0)
    eps_narrow = microstrip_effective_permittivity(1.0e-3, 1.0e-3, 4.0)
    eps_wide = microstrip_effective_permittivity(2.0e-3, 1.0e-3, 4.0)
    z_lower_eps = microstrip_characteristic_impedance(1.0e-3, 1.0e-3, 2.0)
    eps_lower = microstrip_effective_permittivity(1.0e-3, 1.0e-3, 2.0)

    assert z_wide < z_narrow
    assert eps_wide > eps_narrow
    assert z_lower_eps > z_narrow
    assert eps_lower < eps_narrow


@pytest.mark.parametrize(
    "width,height,eps_r",
    [
        (0.0, 1e-3, 4.0),
        (1e-3, -1e-3, 4.0),
        (1e-3, 1e-3, 0.99),
        (math.inf, 1e-3, 4.0),
        (1e-3, math.nan, 4.0),
        (True, 1e-3, 4.0),
        (1e-3, 1e-3, True),
        ("0.001", 1e-3, 4.0),
    ],
)
def test_microstrip_rejects_invalid_inputs(width, height, eps_r):
    with pytest.raises(ValueError):
        microstrip_characteristic_impedance(width, height, eps_r)
    with pytest.raises(ValueError):
        microstrip_effective_permittivity(width, height, eps_r)


def test_skin_depth_copper_reference_and_trends():
    at_1_mhz = skin_depth(1e6, 5.8e7)
    at_100_mhz = skin_depth(100e6, 5.8e7)

    assert at_1_mhz == pytest.approx(66.1e-6, rel=0.01)
    assert at_100_mhz == pytest.approx(at_1_mhz / 10.0, rel=1e-12)
    assert skin_depth(1e6, 2.0 * 5.8e7) < at_1_mhz
    assert skin_depth(1e6, 5.8e7, relative_permeability=4.0) < at_1_mhz


@pytest.mark.parametrize(
    "frequency,conductivity,mu_r",
    [
        (0.0, 5.8e7, 1.0),
        (1e6, 0.0, 1.0),
        (1e6, 5.8e7, -1.0),
        (math.inf, 5.8e7, 1.0),
        (math.nan, 5.8e7, 1.0),
        (True, 5.8e7, 1.0),
    ],
)
def test_skin_depth_rejects_invalid_inputs(frequency, conductivity, mu_r):
    with pytest.raises(ValueError):
        skin_depth(frequency, conductivity, mu_r)


def test_wavelength_cell_limit_reference_and_trends():
    limit = wavelength_cell_limit(1e9, 4.0, points_per_wavelength=10)

    assert limit == pytest.approx(0.0149896229, rel=1e-10)
    assert wavelength_cell_limit(2e9, 4.0, 10) == pytest.approx(limit / 2.0)
    assert wavelength_cell_limit(1e9, 16.0, 10) == pytest.approx(limit / 2.0)
    assert wavelength_cell_limit(1e9, 4.0, 20) == pytest.approx(limit / 2.0)


@pytest.mark.parametrize(
    "frequency,eps_r,points",
    [
        (0.0, 1.0, 10),
        (1e9, 0.9, 10),
        (1e9, 2.0, 0),
        (1e9, 2.0, 2.5),
        (math.inf, 2.0, 10),
        (1e9, math.nan, 10),
    ],
)
def test_wavelength_cell_limit_rejects_invalid_inputs(frequency, eps_r, points):
    with pytest.raises(ValueError):
        wavelength_cell_limit(frequency, eps_r, points)


def test_geometry_cell_spacing_limit():
    assert geometry_cell_spacing_limit(1.2e-3, cells_per_feature=3) == pytest.approx(
        0.4e-3
    )
    assert geometry_cell_spacing_limit(1.2e-3, cells_per_feature=1) == pytest.approx(
        1.2e-3
    )
    assert geometry_cell_spacing_limit(1.2e-3, cells_per_feature=6) < 0.4e-3


@pytest.mark.parametrize(
    "feature,cells",
    [
        (0.0, 3),
        (-1e-3, 3),
        (1e-3, 0),
        (1e-3, 1.5),
        (math.nan, 3),
        (1e-3, True),
    ],
)
def test_geometry_cell_spacing_limit_rejects_invalid_inputs(feature, cells):
    with pytest.raises(ValueError):
        geometry_cell_spacing_limit(feature, cells)


def test_courant_timestep_limit_cubic_and_anisotropic_cells():
    cubic_spacing = 1e-3
    expected_cubic = cubic_spacing / (299_792_458.0 * math.sqrt(3.0))
    assert courant_timestep_limit(cubic_spacing, cubic_spacing, cubic_spacing) == (
        pytest.approx(expected_cubic)
    )

    expected_anisotropic = 1.0 / (
        299_792_458.0
        * math.sqrt(4.0)
        * math.sqrt(1.0 / (1e-3) ** 2 + 1.0 / (2e-3) ** 2 + 1.0 / (4e-3) ** 2)
    )
    assert courant_timestep_limit(
        1e-3, 2e-3, 4e-3, maximum_relative_permittivity=4.0
    ) == pytest.approx(expected_anisotropic)
    assert courant_timestep_limit(
        1e-3, 1e-3, 1e-3, courant_factor=0.5
    ) == pytest.approx(expected_cubic / 2.0)


@pytest.mark.parametrize(
    "dx,dy,dz,eps_r,factor",
    [
        (0.0, 1e-3, 1e-3, 1.0, 1.0),
        (1e-3, -1e-3, 1e-3, 1.0, 1.0),
        (1e-3, 1e-3, math.inf, 1.0, 1.0),
        (1e-3, 1e-3, 1e-3, 0.9, 1.0),
        (1e-3, 1e-3, 1e-3, 1.0, 0.0),
        (1e-3, 1e-3, 1e-3, 1.0, 1.01),
        (1e-3, 1e-3, 1e-3, 1.0, math.nan),
    ],
)
def test_courant_timestep_limit_rejects_invalid_inputs(dx, dy, dz, eps_r, factor):
    with pytest.raises(ValueError):
        courant_timestep_limit(dx, dy, dz, eps_r, factor)
