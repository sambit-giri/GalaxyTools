"""

FUNCTIONS RELATED TO COSMOLOGY

"""
import numpy as np
from scipy.integrate import cumtrapz, trapz, quad
from scipy.interpolate import splrep,splev
from .constants import rhoc0,c
from .run_BoltzmannSolver import *

def rhoc_of_z(z,param):
    """
    Redshift dependence of critical density
    (in comoving units where rho_b=const; same as in AHF)
    """
    Om = param.cosmo.Om
    Ol = 1.0-Om
    return rhoc0*(Om*(1.0+z)**3.0 + Ol)/(1.0+z)**3.0


def hubble(z,param):
    """
    Hubble parameter
    """
    Om = param.cosmo.Om
    Ol = 1.0-Om
    H0 = 100.0*param.cosmo.h0
    return H0 * (Om*(1+z)**3 + (1.0 - Om - Ol)*(1+z)**2 + Ol)**0.5
    

def growth_factor(z, param):
    """
    Growth factor from Longair textbook (Eq. 11.56)
    z: array of redshifts from zmin to zmax
    """
    Om = param.cosmo.Om

    D0 = hubble(0,param) * (5.0*Om/2.0) * quad(lambda a: (a*hubble(1/a-1,param))**(-3), 0.01, 1, epsrel=5e-3, limit=100)[0]
    Dz = []
    for i in range(len(z)):
        Dz += [hubble(z[i],param) * (5.0*Om/2.0) * quad(lambda a: (a*hubble(1/a-1,param))**(-3), 0.01, 1/(1+z[i]), epsrel=5e-3, limit=100)[0]]
    Dz = np.array(Dz)
    return Dz/D0


def comoving_distance(z,param):
    """
    Comoving distance between z[0] and z[-1]
    """
    return cumtrapz(c/hubble(z,param),z,initial=0)  # [Mpc]


def delta_comoving_distance(z0,z1,param):
    """
    Comoving distance between z0 and z1
    if z0 and z1 are close together (no integral)
    """
    zh = (z0+z1)/2
    return (z1-z0)*c/hubble(zh,param)


def T_cmb(z,param):
    """
    CMB temperature
    """
    Tcmb0 = param.cosmo.Tcmb
    return Tcmb0*(1+z)


def read_powerspectrum(param, **info):
    """
    Linear power spectrum from file
    """
    try:
        names='k, P'
        PS = np.genfromtxt(param.file.ps,usecols=(0,1),comments='#',dtype=None, names=names)
    except:
        PS = calc_Plin(param, **info)
    return PS

def calc_Plin(param, **info):
    # print(param.file.ps)
    if param.file.ps.lower()=='camb':
        r = run_camb(param)
    elif param.file.ps.lower()=='class':
        class_ = run_class(param, **info)
        PS = {'k': class_.k, 'P': class_.pk_lin}
    else:
        print('Either choose between CAMB or CLASS Boltmann Solvers or provide a file containing the linear power spectrum.')
        PS = None 
    return PS 

def get_Plin(param, **info):
    return read_powerspectrum(param, **info)

def wf(y,param):
    """
    Window function
    """
    window = param.mf.window
    if (window=='tophat'):
        w = 3.0*(np.sin(y) - y*np.cos(y))/y**3.0
        w[y>100] = 0
    elif (window=='sharpk'):
        w = np.ones(y)
        w[y>1]=0
    elif (window=='gaussian'):
        w = np.exp(-y**2.0/2.0)
    elif (window=='smoothk'):
        beta = param.mf.beta
        w = 1/(1+y**beta)
    else:
        print("ERROR: undefined window function!")
        exit()
    return w


def dwf(y,param):
    """
    Derivative Of window function
    dwf = dwf(kR)/dln(kR)
    """
    window = param.mf.window
    if (window == 'tophat'):
        dw = 3.0*((y**2.0 - 3.0)*np.sin(y) + 3.0*y*np.cos(y))/y**3.0
        dw[y>100] = 0
    elif (window == 'sharpk'):
        """
        delta function (must be accounted for in main code)
        """
        dw = 0.0
    elif (window == 'gaussian'):
        dw = - y**2.0*np.exp(-y**2.0/2.0)
    elif (window=='smoothk'):
        beta = param.mf.beta
        dw = - beta*y**beta/(1+y**beta)**2
    else:
        print("ERROR: undefined window function!")
        exit()
    return dw


def variance(param):
    """
    variance of density perturbations at z=0
    """
    #window function
    window = param.mf.window

    #read in linear power spectrum
    try:
        PS = param.cosmo.plin
        kmin  = min(PS['k'])
        kmax  = max(PS['k'])
    except:
        # names='k, P'
        # PS = np.genfromtxt(param.file.psfct,usecols=(0,1),comments='#',dtype=None, names=names)
        PS = read_powerspectrum(param)
        kmin  = min(PS['k'])
        kmax  = max(PS['k'])

    #set binning
    Nrbin = param.code.Nrbin
    rmin  = param.code.rmin
    rmax  = param.code.rmax
    rbin  = np.logspace(np.log(rmin),np.log(rmax),Nrbin,base=np.e)

    #calculate variance and derivative
    if (window == 'tophat' or window == 'gaussian' or window == 'smoothk'):
        var = []
        dlnvardlnr = []
        for i in range(Nrbin):
            #var
            itd_var = PS['k']**2 * PS['P'] * wf(PS['k']*rbin[i],param)**2
            var += [trapz(itd_var,PS['k'])/(2*np.pi**2)]
            #dlnvar/dlnr
            itd_dvar = PS['k']**2 * PS['P'] * wf(PS['k']*rbin[i],param) * dwf(PS['k']*rbin[i],param)
            dlnvardlnr += [2*np.trapz(itd_dvar,PS['k'])/(2*np.pi**2*var[i])]
        var = np.array(var)
        dlnvardlnr = np.array(dlnvardlnr)
    elif (window == 'sharpk'):
        #var
        Plin_tck = splrep(PS['k'],PS['P'])
        kbin = 1/rbin
        kbin = kbin[::-1]
        var = cumtrapz(kbin**2 * splev(kbin,Plin_tck),kbin,initial=1e-5) / (2*np.pi**2)
        var = var[::-1]
        #dlnvar/dlnr
        dlnvardlnr = -1/(2*np.pi**2*var) * splev(1/rbin,Plin_tck)/rbin**3.0
    else:
        print("ERROR: undefined window function!")
        exit()

    #write varfct to file
    try:
        np.savetxt(param.file.varfct, np.vstack((rbin, var, dlnvardlnr)).T)
    except IOError:
        print('IOERROR: cannot write varfct!')
        exit()

    return rbin, var, dlnvardlnr

