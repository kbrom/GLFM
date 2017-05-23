import numpy as np
import random

import mapping_functions as mf
import matplotlib.pyplot as plt

import time as timeI
import os
import sys
root = os.path.sep.join(os.path.abspath(__file__).split(os.path.sep)[:-2])
sys.path.append(os.path.join(root, 'Ccode/wrapper_python/'))

import GLFMlib # python wrapper library in order to run C++ inference routine
import mapping_functions as mf

import pdb

def infer(data,hidden=dict(), params=dict()):
    """
    Python wrapper to launch inference routine for the GLFM model.
    Inputs:
        data: dictionary containing all input data structures
            X: input data N*D where:
                N = number of observations
                D = number of dimensions
            C: string array indicating types of data ('g': real,'p': positive real,
                'c': categorical; 'o': ordinal; 'n': count data)
        hidden (optional): dictionary containing latent variables
            Z: initial feature activation matrix: N*K
                K = number of latent dimensions
        params (optional): dictionary containing eventual simulation parameters
            bias: indicator of whether to include or not a bias
            s2u: internal auxiliary noise
            s2B: noise variance for prior over elements of matrix B
            alpha: concentration parameter of the Indian Buffet Process
            Niter: number of simulations
            maxK: maximum number of features for memory allocation
            missing: value for missings (should be an integer, not nan)
            verbose: indicator to print more information

    Output:
        hidden:
            Z: feature activation matrix sampled from posterior
            B: observation matrix sampled from posterior
            Theta: auxiliary variables for ordinal data (needed to compute MAP,
                    or posterior PDFs)
            mu: mean parameter for internal transformation
            w: scale parameter for internal transformation
            s2Y: inferred noise variance for pseudo-observations Y
    """
    # complete dictionary params with default values
    params = init_default_params(data, params) # complete unspecified fields

    # check input syntax
    assert(type(data) is dict), "input 'data' should be a dictionary."
    assert(type(hidden) is dict), "input 'hidden' should be a dictionary."
    assert(type(params) is dict), "input 'params' should be a dictionary."
    assert(data.has_key('X')), "dictionary data does not have any matrix X defined."
    assert(data.has_key('C')), "dictionary data does not have any datatype array C defined."
    assert(params['bias'] <= 1), "bias parameter misspecified: should be either 0 or 1."

    N = data['X'].shape[0] # number of observations
    D = data['X'].shape[1] # number of dimensions

    # if Z does not exist, initialize
    if not(hidden.has_key('Z')):
        hidden['Z'] = 1.0*(np.random.rand(N,2) > 0.8)
        if params['bias'] == 1: # add bias if requested
            hidden['Z'] = np.concatenate((np.ones((N,1)), hidden['Z']),axis=1)

    # replace nan by missing values
    data['X'][np.isnan(data['X'])] = params['missing']
    # # dealing with missing data: replace np.nan by -1
    # (xx,yy) = np.where(np.isnan(X)) # find positions where X is nan (i.e. missing data)
    # for r in xrange(len(xx)):
    #     X[xx[r],yy[r]] = -1

    # change labels for categorical and ordinal vars such that categories
    # start counting at 1 and all of them are bigger than 0
    V_offset = np.zeros(D)
    for d in xrange(D):
        if (data['C'][d]=='c' or data['C'][d]=='o'):
            mask = data['X'][:,d] != params['missing']
            V_offset[d] = np.min( data['X'][mask,d] )
            data['X'][mask,d] = data['X'][mask,d] - V_offset[d] + 1

    # eventually, apply external transform specified by the user
    for r in xrange(data['X'].shape[1]):
        if not(params['t'][r] == None): # there is an external transform
            data['X'][:,r] = params['t_1'][r](data['X'][:,r])
            data['C'] = data['C'][:r] + params['ext_dataType'][r] + data['C'][(r+1):]

    # prepare input data for C++ inference routine
    Fin = np.ones(data['X'].shape[1]) # choose internal transform function (for positive)
    Xin = np.ascontiguousarray( data['X'].transpose() ) # specify way to store matrices to be
    Zin = np.ascontiguousarray( hidden['Z'].transpose() ) # compatible with C code
    tic = timeI.time() # start counting time

    # RUN C++ routine
    (Z_out,B_out,Theta_out,mu_out,w_out,s2Y_out) = \
            GLFMlib.infer(Xin, data['C'], Zin, Fin, params['bias'], params['s2u'],\
            params['s2B'], params['alpha'], params['Niter'],\
            params['maxK'], params['missing'], params['verbose'])
    hidden['time'] = timeI.time() - tic
    if params['verbose']:
        print '\n\tElapsed time: %.2f seconds.\n' % hidden['time']

    # wrap output values inside hidden
    hidden['Z'] = Z_out.transpose()
    hidden['B'] = B_out
    hidden['theta'] = Theta_out
    hidden['mu'] = mu_out
    hidden['w'] = w_out
    hidden['s2Y'] = s2Y_out

    hidden['R'] = np.ones(D)
    for d in xrange(D):
        if (data['C'][d] == 'c' or data['C'][d] == 'o'):
            hidden['R'][d] = np.unique( data['X']\
                    [data['X'][:,d] != params['missing'],d] ).shape[0]
    return hidden

def complete(data, hidden=dict(), params=dict()):
    """
    Inputs:
        data: dictionary containing all input data structures
            X: input data N*D where:
                N = number of observations
                D = number of dimensions
            C: string array indicating types of data ('g': real,'p': positive real,
                'c': categorical; 'o': ordinal; 'n': count data)
        hidden (optional): dictionary containing latent variables
            Z: initial feature activation matrix: N*K
                K = number of latent dimensions
        params (optional): dictionary containing eventual simulation parameters
            bias: indicator of whether to include or not a bias
            s2u: internal auxiliary noise
            s2B: noise variance for prior over elements of matrix B
            alpha: concentration parameter of the Indian Buffet Process
            Niter: number of simulations
            maxK: maximum number of features for memory allocation
            missing: value for missings (should be an integer, not nan)
            verbose: indicator to print more information
    Output:
        Xcompl : same numpy array as input X whose missing values have been
                 inferred and completed by the algorithm.
        hidden:
            Z: feature activation matrix sampled from posterior
            B: observation matrix sampled from posterior
            Theta: auxiliary variables for ordinal data (needed to compute MAP,
                    or posterior PDFs)
            mu: mean parameter for internal transformation
            w: scale parameter for internal transformation
            s2Y: inferred noise variance for pseudo-observations Y
    """
    # complete dictionary params
    params = init_default_params(data, params) # complete unspecified fields

    # check input syntax
    assert(type(data) is dict), "input 'data' should be a dictionary."
    assert(type(hidden) is dict), "input 'hidden' should be a dictionary."
    assert(type(params) is dict), "input 'params' should be a dictionary."
    assert(data.has_key('X')), "dictionary data does not have any matrix X defined."
    assert(data.has_key('C')), "dictionary data does not have any datatype array C defined."
    assert(params['bias'] <= 1), "bias parameter misspecified: should be either 0 or 1."

    if sum( sum( (np.isnan(data['X'])) | (data['X']==params['missing']) )) == 0:
        print "The input matrix X has no missing values to complete."
        Xcompl = []
        return (Xcompl,hidden)

    # Run Inference
    hidden = infer(data,hidden,params)

    # Just in case there is any nan (also considered as missing)
    data['X'][np.isnan(data['X'])] = params['missing']

    [xx_miss, yy_miss] = (data['X'] == params['missing']).nonzero()

    Xcompl=np.copy(data['X'])
    for ii in xrange(len(xx_miss)): # for each missing
        if data['X'][xx_miss[ii],yy_miss[ii]] == params['missing']: # will always be the case
            Xcompl[xx_miss[ii],yy_miss[ii]] = computeMAP( data['C'], hidden['Z'][xx_miss[ii],:], hidden, params, [ yy_miss[ii] ] )
    return (Xcompl,hidden)

def computeMAP(C, Zp, hidden, params=dict(), idxsD=[]):
    """
    Function to generate the MAP solution corresponding to patterns in Zp
    Inputs:
      C: 1*D string with data types, D = number of dimensions
      Zp: P * K matrix of feature activation for which to compute the MAP estimate
          (P is the number of obs.)
      hidden: structure with latent variables learned by the model
          - B: latent feature matrix (D * K * maxR)  where
                  D: number of dimensions
                  K: number of latent variables
               maxR: maximum number of categories across all dimensions
          - mu: 1*D shift parameter
          - w:  1*D scale parameter
          - s2Y: 1*D inferred noise variance for each dimension of pseudo-observations
          - theta: D*maxR matrix of auxiliary vars (for ordinal variables)
    ----------------(optional) ------------------
          - idxsD: dimensions to infer

    Outputs:
      X_map: P*Di matrix with MAP estimate where Di = length(idxsD)
    """
    if (len(idxsD) == 0): # no dimension specified, infer all dimensions
        idxsD = range(hidden['B'].shape[0])

    if len(Zp.shape) == 1: # Zp is just 1 vector
        P = 1
        K2 = Zp.shape[0]
    else:
        P = Zp.shape[0]
        K2 = Zp.shape[1]
    K = hidden['B'].shape[1] # number of latent features
    assert (K2 == K), "Incongruent sizes between Zp and hidden['B']: number of latent variables should not be different"

    X_map = np.zeros((P,len(idxsD))) # output matrix
    for dd in xrange(len(idxsD)): # for each dimension
        d = idxsD[dd]
        if params.has_key('t'): # if external transformations have been defined
            if not(params['t'][d] == None): # there is an external transform for data type d
                C = C[:d] + params['ext_dataType'][d] + C[(d+1):]

        if not(C[d] == 'c'):
            aux = np.inner(Zp, hidden['B'][d,:,0])

        if C[d] == 'g':
            X_map[:,dd] = mf.f_g( aux, hidden['mu'][d], hidden['w'][d] )
        elif C[d] == 'p':
            X_map[:,dd] = mf.f_p( aux, hidden['mu'][d], hidden['w'][d] )
        elif C[d] == 'n':
            X_map[:,dd] = mf.f_n( aux, hidden['mu'][d], hidden['w'][d] )
        elif C[d] == 'c':
            X_map[:,dd] = mf.f_c( np.inner(Zp, hidden['B'][d,:,\
                    range(int(hidden['R'][d])) ]) )
        elif C[d] == 'o':
            X_map[:,dd] = mf.f_o( aux, hidden['theta'][d,range(int(hidden['R'][d]-1))] )
        else:
            raise ValueError('Unknown data type')
        if (sum(np.isnan(X_map[:,dd])) > 0):
            raise ValueError('Some values are nan!')
        if params.has_key('t'):
            if not(params['t'][d] == None): # there is an external transform for data type d
                X_map[:,dd] = params['t'][d]( X_map[:,dd] )
    return X_map

def computePDF(data, Zp, hidden, params, d):
    """
    Function to compute probability density function for dimension d
    """
    data['X'][np.isnan(data['X'][:,d]),d] = params['missing_val']

    # compute x-domain [mm MM] to compute pdf
    mm = np.min(data['X'][not(data['X'][:,d] == params['missing']), d]) # min value
    MM = np.max(data['X'][not(data['X'][:,d] == params['missing']), d]) # max value

    if (not(params['t'][d]) == None): # if there is an external transformation
        data['C'][d] = params['ext_dataType'][d]
        mm = params['t_1'][d](mm)
        MM = params['t_1'][d](MM)

    if len(Zp.shape) == 1: # Zp is just 1 vector
        P = 1
        K2 = Zp.shape[0]
    else:
        P = Zp.shape[0]
        K2 = Zp.shape[1]
    K = hidden['B'].shape[1]
    assert (K2 == K), "Incongruent sizes between Zp and hidden['B']: number of latent variables should not be different"

    if (data['C'][d] == 'g') or (data['C'][d] == 'p'):
        if not(params.has_key('numS')):
            params['numS'] = 100
        xd = np.linspace(mm, MM, num=params['numS'])
    elif (data['C'][d] == 'n'):
        xd = range(mm,MM+1)
        params['numS'] = len(xd)
    else:
        xd = np.unique(data['X'][not(data['X'][:,d] == params['missing']), d])
        params['numS'] = len(xd) # number of labels for categories or ordinal data
    pdf = np.zeros((P,params['numS']))

    for p in xrange(P):
        if data['C'][d] == 'g':
            pdf[p,:] = mf.pdf_g(xd,Zp[p,:], np.squeeze(hidden['B'][d,:]), hidden['mu'][d], hidden['w'][d], hidden['s2Y'][d], params)
        elif data['C'][d] == 'p':
            pdf[p,:] = mf.pdf_p(xd,Zp[p,:], np.squeeze(hidden['B'][d,:]), hidden['mu'][d], hidden['w'][d], hidden['s2Y'][d], params)
        elif data['C'][d] == 'n':
            pdf[p,:] = mf.pdf_n(xd,Zp[p,:], np.squeeze(hidden['B'][d,:]), hidden['mu'][d], hidden['w'][d], hidden['s2Y'][d], params)
        elif data['C'][d] == 'c':
            pdf[p,:] = mf.pdf_c(Zp[p,:], np.squeeze(hidden['B'][d,:,range(hidden['R'][d])]), hidden['s2Y'][d])
        elif data['C'][d] == 'o':
            pdf[p,:] = mf.pdf_o(Zp[p,:], squeeze(hidden['B'][d,:]), hidden['theta'][d,range(hidden['R'][d]-1)], hidden['s2Y'][d])
        else:
            raise ValueError('Unknown data type')
        assert (np.sum(np.isnan(pdf)) == 0), "Some values are nan!"

    if params.has_key('t'):
        if not(params['t'] == None): # we have used a special transform beforehand
            xd = params['t'][d](xd) # if there was an external transformation, transform pdf
            pdf = pdf * np.abs( params['dt_1'][d](xd) )
    return (xd,pdf)

def get_feature_patterns(Z):
    """
    Function to compute list of activation patterns. Returns sorted list
    Input:
        Z: N*K binary matrix
    Outputs:
        patterns: numP*K: list of patterns
        C: assignment vector of length N*1 with pattern id for each observation
        L: numP*1 vector with num. of observations per pattern
    """
    N = Z.shape[0]
    C = np.zeros(N)

    patterns = np.vstack({tuple(row) for row in Z})
    numP = patterns.shape[0]
    L = np.zeros(numP)
    for r in xrange(numP): # for each pattern
        pat = patterns[r,:]
        mask = np.sum(np.tile(pat,(N,1)) == Z, axis=1) == Z.shape[1]
        C[mask] = r
        L[r] = sum(mask)
        #print '%d. %s: %d' % (r, str(patterns[r,:]), L[r])

    # sort arrays
    idxs = L.argsort()
    idxs = np.flipud(idxs)
    L = L[idxs]
    C = C[idxs]
    patterns = patterns[idxs,:]

    print '\n'
    for r in xrange(numP): # for each pattern
        print '%d. %s: %d' % (r, str(patterns[r,:]), L[r])

    return (patterns,C,L)

def plot_dim_1feat(X,B,Theta,C,d,k,s2Y,s2u,missing=-1,catlabel=[],xlabel=[]):
    """
    Function to plot an individual dimension of feature matrix B
    Inputs:
        X: observation matrix of dimensions (D,N)
        B: (D,Kest,maxR) ndarray
        C: datatype vector - str of length D
        d: dimension to plot
        k: feature to consider
    Output:
        void
    """
    plt.figure()
    plt.xlabel(xlabel)

    (D,Kest,maxR) = B.shape
    Xd = data['X'][d,:]
    data['C'] = data['C'][d]
    if k<0 or k>Kest:
        print('Error: k index should be bigger than o and smaller than Kest')
    if np.isnan(missing):
        mask = np.where(not(np.isnan(Xd)))[0]
    else:
        mask = np.where(Xd != missing)[0]
    if data['C'] == 'g':
        numP = 100 # number of points to plot
        xx = np.linspace( min(Xd[mask]), max(Xd[mask]), numP )
        Zn = np.zeros(Kest)
        Zn[k] = 1
        Bdv = B[d,:,0]
        pdf = mf.pdf_real(xx, Zn,Bdv,s2Y,s2u)
        plt.plot(xx,pdf)

    elif data['C'] == 'p':
        numP = 100 # number of points to plot
        xx = np.linspace( min(Xd[mask]), max(Xd[mask]), numP )
        Zn = np.zeros(Kest)
        Zn[k] = 1
        Bdv = B[d,:,0]
        w = 2.0 / max(Xd[mask]) # TODO: put function handler
        pdf = mf.pdf_pos(xx,Zn,Bdv,w,s2Y,s2u,lambda x,w: mf.fpos_1(x,w), \
                lambda x,w: mf.dfpos_1(x, w));
        plt.plot(xx,pdf)

    elif data['C'] == 'n':
        xx = np.arange( min(Xd[mask]), max(Xd[mask])+1)
        Zn = np.zeros(Kest)
        Zn[k] = 1
        Bdv = B[d,:,0]
        w = 2.0 / max(Xd[mask]) # TODO: put function handler
        pdf = mf.pdf_count(xx,Zn,Bdv,w,s2Y, lambda x,w: mf.fpos_1(x,w))
        plt.stem(xx,pdf)

    elif data['C'] == 'c':
        R = len( np.unique(Xd[mask]) )
        Zn = np.zeros(Kest)
        Zn[k] = 1
        Bdv = np.squeeze(B[d,:,:]) # TODO: Review that size = [K*R]
        pdf = mf.pdf_cat(Zn,Bdv,s2u,R)
        bar_width = 0.35
        index = np.arange(len(pdf))
        plt.bar(index,pdf,bar_width)
        plt.xticks(index + bar_width / 2, catlabel, rotation='vertical')

    elif data['C'] == 'o':
        a = 1
        # TODO
    else:
        print 'Unknown datatype'
    plt.ion()
    plt.show()
    plt.pause(0.0001)
    return

def plot_dim(X,B,Theta,C,d,Zp,s2Y,s2u,missing=-1,catlabel=[],xlabel=[]):
    """
    Function to plot an individual dimension of feature matrix B
    Inputs:
        X: observation matrix of dimensions (D,N)
        B: (D,Kest,maxR) ndarray
        C: datatype vector - str of length D
        d: dimension to plot
    Output:
        void
    """
    if (Zp.shape[1] != B.shape[1]):
        print 'Error: Sizes of Zp and B are inconsistent'

    colors = ['r','b','g','m','g']
    plt.figure()       # create new figure
    plt.xlabel(xlabel) # add x legend
    #print xlabel

    (D,Kest,maxR) = B.shape
    Xd = data['X'][d,:]
    data['C'] = data['C'][d]
    # only consider values in dimension d which are not missing
    if np.isnan(missing):
        mask = np.where(not(np.isnan(Xd)))[0]
    else:
        mask = np.where(Xd != missing)[0]
    (numPatterns,Kest) = Zp.shape
    if data['C'] == 'g':
        numP = 100 # number of points to plot
        xx = np.linspace( min(Xd[mask]), max(Xd[mask]), numP )
        Bdv = B[d,:,0]
        for p in xrange(numPatterns):
            Zn = np.squeeze(Zp[p,:]) # TODO: Verify dimensions
            pdf = mf.pdf_real(xx, Zn,Bdv,s2Y,s2u)
            plt.plot(xx,pdf,label=str(Zn))

    elif data['C'] == 'p':
        numP = 100 # number of points to plot
        xx = np.linspace( min(Xd[mask]), max(Xd[mask]), numP )
        Bdv = B[d,:,0]
        w = 2.0 / max(Xd[mask]) # TODO: put function handler
        for p in xrange(numPatterns):
            Zn = np.squeeze(Zp[p,:]) # TODO: Verify dimensions
            pdf = mf.pdf_pos(xx,Zn,Bdv,w,s2Y,s2u,lambda x,w: mf.fpos_1(x,w), \
                lambda x,w: mf.dfpos_1(x, w))
            plt.plot(xx,pdf,colors[p],label=str(Zn))

    elif data['C'] == 'n':
        xx = np.arange( min(Xd[mask]), max(Xd[mask])+1)
        Bdv = B[d,:,0]
        w = 2.0 / max(Xd[mask]) # TODO: put function handler
        for p in xrange(numPatterns):
            Zn = np.squeeze(Zp[p,:]) # TODO: Verify dimensions
            pdf = mf.pdf_count(xx,Zn,Bdv,w,s2Y, lambda x,w: mf.fpos_1(x,w))
            plt.stem(xx,pdf,colors[p], label=str(Zn))

    elif data['C'] == 'c':
        R = len( np.unique(Xd[mask]) )
        Bdv = np.squeeze(B[d,:,:]) # TODO: Review that size = [K*R]
        bar_width = 0.6/numPatterns
        for p in xrange(numPatterns):
            Zn = np.squeeze(Zp[p,:]) # TODO: Verify dimensions
            pdf = mf.pdf_cat(Zn,Bdv,s2u,R)
            index = np.arange(len(pdf))
            plt.bar(index+p*bar_width,pdf,width=bar_width,color=colors[p]) #, label=str(Zn))
        plt.xticks(index + bar_width / 2, catlabel, rotation='vertical')
#ax.bar(x-0.2, y,width=0.2,color='b',align='center')
#ax.bar(x, z,width=0.2,color='g',align='center')

    elif data['C'] == 'o':
        print 'This category is currently under development'
        a = 1
        # TODO
    else:
        print 'Unknown datatype'
    plt.legend()
    #plt.ion()
    plt.show()
    plt.pause(0.0001)

    return


def init_default_params(data, params):
    """
    Initialize of complete dictionary params
    Input:
        data: dict with database
        params: dict to complete with default values
    Output:
        same data structure: params
    """
    # s2u=0.001
    D = data['X'].shape[1]
    if not(params.has_key('missing')):
        params['missing'] = -1
    if not(params.has_key('alpha')):
        params['alpha'] = 1
    if not(params.has_key('bias')):
        params['bias'] = 0
    if not(params.has_key('s2u')):
        params['s2u'] = 0.01
    if not(params.has_key('s2B')):
        params['s2B'] = 1
    if not(params.has_key('Niter')):
        params['Niter'] = 1000
    if not(params.has_key('maxK')):
        params['maxK'] = D
    if not(params.has_key('verbose')):
        params['verbose'] = 1
    if not(params.has_key('numS')):
        params['numS'] = 1

    # parameters for optional external transformation
    if not(params.has_key('t')):
        params['t'] = [None] * D
    if not(params.has_key('t_1')):
        params['t_1'] = [None] * D
    if not(params.has_key('dt_1')):
        params['dt_1'] = [None] * D
    return params
