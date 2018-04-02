import numpy as np
import scipy.sparse as sprs
import scipy.sparse.csgraph as spgr
from openpnm.algorithms import GenericAlgorithm
from openpnm.core import logging
logger = logging.getLogger(__name__)


class GenericTransport(GenericAlgorithm):
    r"""
    """

    def __init__(self, project=None, network=None, phase=None, settings={},
                 **kwargs):
        # Set some default settings
        self.settings.update({'phase': None,
                              'conductance': None,
                              'quantity': None,
                              'solver': 'spsolve'})
        self.settings.update(settings)
        if phase is not None:
            self.settings['phase'] = phase.name

        if network is not None:
            project = network.project

        super().__init__(project=project, **kwargs)
        self.A = None
        self._pure_A = None
        self.b = None
        self._pure_b = None

    def set_dirchlet_BC(self, pores, values):
        r"""
        Apply *Dirichlet* boundary conditons to the specified pore locations.
        Dirichlet conditions refer to constant *quantity* (e.g. pressure).

        Parameters
        ----------
        pores : array_like
            The pore indices where the condition should be applied

        values : scalar or array_like
            The value to of the boundary condition.  If a scalar is supplied
            it is assigne to all locations, and if a vector is applied it
            corresponds directy to the locations given in ``pores``.

        Notes
        -----
        The definition of ``quantity`` is specified in the algorithm's
        ``settings``, e.g. ``alg.settings['quentity'] = 'pore.pressure'``.
        """
        self.set_BC(pores=pores, bctype='dirichlet', bcvalues=values,
                    mode='merge')

    def set_neumann_BC(self, pores, values):
        r"""
        Apply *Neumann*-type boundary conditons to the specified pore
        locations. Neumann conditions technnically refer to the *gradient* of
        the *quantity* (e.g. dP/dz), while in OpenPNM this means the flow-rate
        of the quantity, which is the gradient multiplied by the conductance
        (e.g n = g dP/dz).

        Parameters
        ----------
        pores : array_like
            The pore indices where the condition should be applied

        values : scalar or array_like
            The value to of the boundary condition.  If a scalar is supplied
            it is assigne to all locations, and if a vector is applied it
            corresponds directy to the locations given in ``pores``.

        Notes
        -----
        The definition of ``quantity`` is specified in the algorithm's
        ``settings``, e.g. ``alg.settings['quentity'] = 'pore.pressure'``.
        """
        self.set_BC(pores=pores, bctype='neumann', bcvalues=values,
                    mode='merge')

    def set_BC(self, pores, bctype, bcvalues=None, mode='merge'):
        r"""
        Apply boundary conditions to specified pores

        Parameters
        ----------
        pores : array_like
            The pores where the boundary conditions should be applied

        bctype : string
            Specifies the type or the name of boundary condition to apply. The
            types can be one one of the following:

            - *'dirichlet'* : Specify the quantity in each location
            - *'neumann'* : Specify the flow rate into each location

        bcvalues : int or array_like
            The boundary value to apply, such as concentration or rate.  If
            a single value is given, it's assumed to apply to all locations.
            Different values can be applied to all pores in the form of an
            array of the same length as ``pores``.

        mode : string, optional
            Controls how the conditions are applied.  Options are:

            - *'merge'*: (Default) Adds supplied boundary conditions to already
            existing conditions.

        Notes
        -----
        It is not possible to have multiple boundary conditions for a
        specified location in one algorithm. Use ``mode='remove'`` to
        clear existing BCs before applying new ones or ``mode='overwrite'``
        which removes all existing BC's before applying the new ones.

        Instead of using ``mode='remove'`` you can also set certain locations
        to NaN using ``mode='merge'``, which is equivalent to removing the BCs
        from those locations.

        """
        # Hijack the parse_mode function to verify bctype argument
        bctype = self._parse_mode(bctype, allowed=['dirichlet', 'neumann'],
                                  single=True)
        mode = self._parse_mode(mode, allowed=['merge', 'overwrite', 'remove'],
                                single=True)
        pores = self._parse_indices(pores)

        values = np.array(bcvalues)
        if values.size > 1 and values.size != pores.size:
            raise Exception('The number of boundary values must match the ' +
                            'number of locations')

        # Label pores where a boundary condition will be applied
        if ('pore.'+bctype not in self.keys()) or (mode == 'overwrite'):
            self['pore.'+bctype] = False
        self['pore.'+bctype][pores] = True

        # Store boundary values
        if ('pore.'+bctype+'_value' not in self.keys()) or \
           (mode == 'overwrite'):
            self['pore.'+bctype+'_value'] = np.nan
        self['pore.'+bctype+'_value'][pores] = values

    def remove_BC(self, pores=None):
        r"""
        Removes all boundary conditions from the specified pores

        Parameters
        ----------
        pores : array_like
            The pores from which boundary conditions are to be removed.  If no
            pores are specified, then BCs are removed from all pores. No error
            is thrown if the provided pores do not have any BCs assigned.
        """
        if pores is None:
            pores = self.Ps
        if 'pore.dirichlet' in self.keys():
            self['pore.dirichlet'][pores] = False
            self['pore.dirichlet_value'][pores] = np.nan
        if 'pore.neumann' in self.keys():
            self['pore.neumann'][pores] = False
            self['pore.neumann_value'][pores] = np.nan

    def _build_A(self, force=False):
        r"""
        Builds the coefficient matrix based on conductances between pores.
        The conductance to use is specified in the algorithm's ``settings``
        under ``conductance``.  In subclasses (e.g. ``FickianDiffusion``)
        this is set by default, though it can be overwritten.

        Parameters
        ----------
        force : Boolean (default is ``False)
            If set to ``True`` then the A matrix is built from new.  If
            ``False`` (the default), a cached version of A is returned.  The
            cached version is *clean* in the sense that no boundary conditions
            or sources terms have been added to it.
        """
        if force:
            self._pure_A = None
        if self._pure_A is None:
            network = self.project.network
            phase = self.project.phases()[self.settings['phase']]
            g = phase[self.settings['conductance']]
            am = network.create_adjacency_matrix(weights=g, fmt='coo')
            self._pure_A = spgr.laplacian(am)
        self.A = self._pure_A.copy()

    def _build_b(self, force=False):
        r"""
        Builds the RHS matrix, without applying any boundary conditions or
        source terms. This method is trivial an basically creates a column
        vector of 0's.

        Parameters
        ----------
        force : Boolean (default is ``False``)
            If set to ``True`` then the b matrix is built from new.  If
            ``False`` (the default), a cached version of b is returned.  The
            cached version is *clean* in the sense that no boundary conditions
            or sources terms have been added to it.
        """
        if force:
            self._pure_b = None
        if self._pure_b is None:
            b = np.zeros(shape=(self.Np, ), dtype=float)  # Create vector of 0s
            self._pure_b = b
        self.b = self._pure_b.copy()

    def _apply_BCs(self):
        r"""
        Applies all the boundary conditions that have been specified, by
        adding values to the *A* and *b* matrices.

        """
        self._build_A()
        self._build_b()
        if 'pore.neumann' in self.keys():
            # Update b
            ind = self['pore.neumann']
            self.b[ind] = self['pore.neumann_value'][ind]
        if 'pore.dirichlet' in self.keys():
            # Update b
            ind = self['pore.dirichlet']
            self.b[ind] = self['pore.dirichlet_value'][ind]
            # Update A
            # Find all entries on rows associated with dirichlet pores
            P_bc = self.toindices(self['pore.dirichlet'])
            indrow = np.in1d(self.A.row, P_bc)
            self.A.data[indrow] = 0  # Remove entries from A for all BC rows
            datadiag = self.A.diagonal()  # Add diagonal entries back into A
            datadiag[P_bc] = np.ones_like(P_bc, dtype=float)
            self.A.setdiag(datadiag)
            self.A.eliminate_zeros()  # Remove 0 entries

    def run(self):
        r"""
        Builds the A and b matrices, and calls the solver specified in the
        ``settings`` attribute.

        Parameters
        ----------
        x : ND-array
            Initial guess of unknown variable

        Returns
        -------
        Nothing is returned...the solution is stored on the objecxt under
        ``pore.quantity`` where *quantity* is specified in the ``settings``
        attribute.

        """
        print('―'*80)
        print('Running GenericTransport')
        self._run_generic()

    def _run_generic(self):
        self._apply_BCs()
        x_new = self._solve()
        self[self.settings['quantity']] = x_new

    def _solve(self, A=None, b=None):
        r"""
        Sends the A and b matrices to the specified solver, and solves for *x*
        given the boundary conditions, and source terms based on the present
        value of *x*.  This method does NOT iterate to solve for non-linear
        source terms or march time steps.

        Parameters
        ----------
        A : sparse matrix
            The coefficient matrix in sparse format. If not specified, then
            it uses  the ``A`` matrix attached to the object.

        b : ND-array
            The RHS matrix in any format.  If not specified, then it uses
            the ``b`` matrix attached to the object.

        Notes
        -----
        The solver used here is specified in the ``settings`` attribute of the
        algorithm.

        """
        if A is None:
            A = self.A
            if A is None:
                raise Exception('The A matrix has not been built yet')
        if b is None:
            b = self.b
            if b is None:
                raise Exception('The b matrix has not been built yet')
        solver = getattr(sprs.linalg, self.settings['solver'])
        x = solver(A=A.tocsr(), b=b)
        return x

    def results(self):
        r"""
        Fetches the calculated quantity from the algorithm and returns it as
        an array.
        """
        quantity = self.settings['quantity']
        d = {quantity: self[quantity]}
        return d

    def rate(self, pores=None, mode='group'):
        r"""
        Calculates the net rate of material moving into a given set of pores.

        Parameters
        ----------
        pores : array_like
            The pores for which the rate should be calculated

        mode : string, optional
            Controls how to return the rate.  Options are:

            *'group'*: (default) Teturns the cumulative rate of material
            moving into the given set of pores

            *'single'* : Calculates the rate for each pore individually

        Notes
        -----
        A negative rate indicates material moving into the pore or pores, such
        as material being consumed.
        """
        network = self.project.network
        phase = self.project.phases[self.settings['phase']]
        conductance = phase[self.settings['conductance']]
        quantity = self[self.settings['quantity']]
        pores = self._parse_indices(pores)
        R = []
        if mode == 'group':
            t = network.find_neighbor_throats(pores, flatten=True,
                                              mode='not_intersection')
            throat_group_num = 1
        elif mode == 'single':
            t = network.find_neighbor_throats(pores, flatten=False,
                                              mode='not_intersection')
            throat_group_num = np.shape(t)[0]
        for i in np.r_[0: throat_group_num]:
            if mode == 'group':
                throats = t
                P = pores
            elif mode == 'single':
                throats = t[i]
                P = pores[i]
            p1 = network.find_connected_pores(throats)[:, 0]
            p2 = network.find_connected_pores(throats)[:, 1]
            pores1 = np.copy(p1)
            pores2 = np.copy(p2)
            # Changes to pores1 and pores2 to make them as inner/outer pores
            pores1[~np.in1d(p1, P)] = p2[~np.in1d(p1, P)]
            pores2[~np.in1d(p1, P)] = p1[~np.in1d(p1, P)]
            X1 = quantity[pores1]
            X2 = quantity[pores2]
            g = conductance[throats]
            R.append(np.sum(np.multiply(g, (X2 - X1))))
        return np.array(R, ndmin=1)

    def _calc_eff_prop(self):
        r"""
        Returns the main parameters for calculating the effective
        property in a linear transport equation.  It also checks for the
        proper boundary conditions, inlets and outlets.
        """
        network = self.project.network
        if self.settings['quantity'] not in self.keys():
            raise Exception('The algorit hm has not been run yet. Cannot ' +
                            'calculate effective property.')

        # Determine boundary conditions by analyzing algorithm object
        Ps = self.pores('pore.dirichlet')
        BCs = np.unique(self['pore.dirichlet_value'][Ps])
        inlets = np.where(self['pore.dirichlet_value'] == np.amax(BCs))[0]
        outlets = np.where(self['pore.dirichlet_value'] == np.amin(BCs))[0]

        # Fetch area and length of domain
        A = network.domain_area(face=inlets)
        L = network.domain_length(face_1=inlets, face_2=outlets)
        flow = self.rate(pores=inlets)
        D = np.sum(flow)*L/A/(BCs[0] - BCs[1])
        return D
