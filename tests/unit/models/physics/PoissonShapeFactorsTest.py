import openpnm as op
from numpy.testing import assert_allclose
from numpy import pi
import numpy as np


class PoissonShapeFactorsTest:
    def setup_class(self):
        self.net = op.network.Cubic(shape=[4, 4, 4])
        self.geo = op.geometry.GenericGeometry(network=self.net,
                                               pores=self.net.Ps,
                                               throats=self.net.Ts)
        self.phase = op.phases.GenericPhase(network=self.net)
        self.phys = op.physics.GenericPhysics(network=self.net,
                                              phase=self.phase,
                                              geometry=self.geo)
        self.geo['pore.diameter'] = 0.5
        self.geo['pore.area'] = pi/4*0.5**2
        self.geo['throat.diameter'] = 0.35
        self.geo['throat.area'] = pi/4*0.35**2
        self.geo['throat.conduit_lengths.pore1'] = 0.2
        self.geo['throat.conduit_lengths.throat'] = 0.7
        self.geo['throat.conduit_lengths.pore2'] = 0.15

    def test_ball_and_stick(self):
        mod = op.models.physics.poisson_shape_factors.ball_and_stick
        self.phys.add_model(propname='throat.poisson_shape_factors',
                            model=mod)
        self.phys.regenerate_models()
        SF1 = self.phys['throat.poisson_shape_factors.pore1'].mean()
        SF2 = self.phys['throat.poisson_shape_factors.pore2'].mean()
        SFt = self.phys['throat.poisson_shape_factors.throat'].mean()
        assert_allclose(SF1, desired=0.72819138)
        assert_allclose(SF2, desired=0.86561702)
        assert_allclose(SFt, desired=1.0)

    def test_ball_and_stick_equal_pore_and_throat_diameter(self):
        self.geo['throat.diameter'] = 0.5
        self.geo['throat.area'] = pi/4*1**2
        mod = op.models.physics.poisson_shape_factors.ball_and_stick
        self.phys.add_model(propname='throat.poisson_shape_factors',
                            model=mod)
        self.phys.regenerate_models()
        SF1 = self.phys['throat.poisson_shape_factors.pore1'].mean()
        SF2 = self.phys['throat.poisson_shape_factors.pore2'].mean()
        SFt = self.phys['throat.poisson_shape_factors.throat'].mean()
        assert_allclose(SF1, desired=1.0)
        assert_allclose(SF2, desired=1.0)
        assert_allclose(SFt, desired=1.0)
        # Reverting changes
        self.geo['throat.diameter'] = 0.35
        self.geo['throat.area'] = pi/4*0.35**2

    def test_ball_and_stick_with_boundary_pores(self):
        boundary_pores = [1, 8, 12, 55]
        conns = self.net['throat.conns']
        BP1 = np.in1d(conns[:, 0], boundary_pores)
        BP2 = np.in1d(conns[:, 1], boundary_pores)
        self.geo['throat.conduit_lengths.pore1'][BP1] = 0
        self.geo['throat.conduit_lengths.pore2'][BP2] = 0
        mod = op.models.physics.poisson_shape_factors.ball_and_stick
        self.phys.add_model(propname='throat.poisson_shape_factors',
                            model=mod)
        self.phys.regenerate_models()
        SF1_BP = self.phys['throat.poisson_shape_factors.pore1'][BP1].mean()
        SF2_BP = self.phys['throat.poisson_shape_factors.pore2'][BP2].mean()
        assert_allclose(SF1_BP, desired=1.0)
        assert_allclose(SF2_BP, desired=1.0)
        # Reverting changes
        self.geo['throat.conduit_lengths.pore1'] = 0.2
        self.geo['throat.conduit_lengths.pore2'] = 0.15

    def test_conical_frustum_and_stick(self):
        mod = op.models.physics.poisson_shape_factors.conical_frustum_and_stick
        self.phys.add_model(propname='throat.poisson_shape_factors',
                            model=mod)
        self.phys.regenerate_models()
        SF1 = self.phys['throat.poisson_shape_factors.pore1'].mean()
        SF2 = self.phys['throat.poisson_shape_factors.pore2'].mean()
        SFt = self.phys['throat.poisson_shape_factors.throat'].mean()
        assert_allclose(SF1, desired=0.7)
        assert_allclose(SF2, desired=0.7)
        assert_allclose(SFt, desired=1.0)

    def test_conical_frustum_and_stick_equal_pore_and_throat_diameter(self):
        self.geo['throat.diameter'] = 0.5
        self.geo['throat.area'] = pi/4*1**2
        mod = op.models.physics.poisson_shape_factors.conical_frustum_and_stick
        self.phys.add_model(propname='throat.poisson_shape_factors',
                            model=mod)
        self.phys.regenerate_models()
        SF1 = self.phys['throat.poisson_shape_factors.pore1'].mean()
        SF2 = self.phys['throat.poisson_shape_factors.pore2'].mean()
        SFt = self.phys['throat.poisson_shape_factors.throat'].mean()
        assert_allclose(SF1, desired=1.0)
        assert_allclose(SF2, desired=1.0)
        assert_allclose(SFt, desired=1.0)
        # Reverting changes
        self.geo['throat.diameter'] = 0.35
        self.geo['throat.area'] = pi/4*0.35**2

    def test_conical_frustum_and_stick_with_boundary_pores(self):
        boundary_pores = [1, 8, 12, 55]
        conns = self.net['throat.conns']
        BP1 = np.in1d(conns[:, 0], boundary_pores)
        BP2 = np.in1d(conns[:, 1], boundary_pores)
        self.geo['throat.conduit_lengths.pore1'][BP1] = 0
        self.geo['throat.conduit_lengths.pore2'][BP2] = 0
        mod = op.models.physics.poisson_shape_factors.conical_frustum_and_stick
        self.phys.add_model(propname='throat.poisson_shape_factors',
                            model=mod)
        self.phys.regenerate_models()
        SF1_BP = self.phys['throat.poisson_shape_factors.pore1'][BP1].mean()
        SF2_BP = self.phys['throat.poisson_shape_factors.pore2'][BP2].mean()
        assert_allclose(SF1_BP, desired=1.0)
        assert_allclose(SF2_BP, desired=1.0)
        # Reverting changes
        self.geo['throat.conduit_lengths.pore1'] = 0.2
        self.geo['throat.conduit_lengths.pore2'] = 0.15


if __name__ == '__main__':

    t = PoissonShapeFactorsTest()
    self = t
    t.setup_class()
    for item in t.__dir__():
        if item.startswith('test'):
            print('running test: '+item)
            t.__getattribute__(item)()
