import sys
sys.path.append('../')

import logging
import os
import itertools
from gensim import utils
try:
    from gensim.models.word2vec_inner import MAX_WORDS_IN_BATCH
except ImportError:
    # failed... fall back to plain numpy (20-80x slower training than the above)
    MAX_WORDS_IN_BATCH = 10000

import gzip
import bz2
import pickle
import numpy as np

from composes.semantic_space.space import Space 
from collections import defaultdict
from composes.utils import io_utils
from scipy.sparse import coo_matrix, csr_matrix
from composes.matrix.sparse_matrix import SparseMatrix
from composes.matrix.dense_matrix import DenseMatrix


# To-do: should be renamed and restructured
def save_pkl_files(dsm, dsm_prefix, save_in_one_file=False, save_as_w2v=False):
    """
    Save semantic space (from DISSECT package) to different formats.
    :param dsm: the semantic space
    :param dsm_prefix: the prefix for the output files
    :param save_in_one_file: whether to save as one file (pkl or w2v) or separate files (npz for matrix and pkl for rows and columns)
    :param save_as_w2v: given save_in_one_file=True, whether to save it in w2v format or pkl
    """
    
    # Save in a single file (for small spaces)
    if save_in_one_file:
        # only useful for dense spaces
        if save_as_w2v:
            rows = np.array(dsm.cooccurrence_matrix.get_mat()).astype(object)
            id2row = np.array([word.decode('utf-8') for word in dsm.get_id2row()])
            r, d = rows.shape
            id2row = id2row.reshape(-1,1)
            rows = np.concatenate((id2row, rows), axis=1)
            np.savetxt(dsm_prefix + '.w2v', rows, fmt=["%s"] + ['%.16g',]*d, delimiter=' ', newline='\n', header='%d %d' %(r, d), comments='', encoding='utf-8')
        else:
            io_utils.save(dsm, dsm_prefix + '.pkl')
            
    # Save in multiple files: npz for the matrix and pkl for the other data members of Space
    else:
        mat = coo_matrix(dsm.cooccurrence_matrix.get_mat())
        np.savez_compressed(dsm_prefix + '.npz', data=mat.data, row=mat.row, col=mat.col, shape=mat.shape)

        with open(dsm_prefix + '_row2id.pkl', 'wb') as f_out:
            pickle.dump(dsm._row2id, f_out, 2)

        with open(dsm_prefix + '_id2row.pkl', 'wb') as f_out:
            pickle.dump(dsm._id2row, f_out, 2)

        with open(dsm_prefix + '_column2id.pkl', 'wb') as f_out:
            pickle.dump(dsm._column2id, f_out, 2)

        with open(dsm_prefix + '_id2column.pkl', 'wb') as f_out:
            pickle.dump(dsm._id2column, f_out, 2)


def load_pkl_files(dsm_prefix):
    """
    Load the space from either a single pkl file or numerous files.
    :param dsm_prefix: the prefix of the input files (.pkl, .rows, .cols)
    """

    # Check whether there is a single pickle file for the Space object
    if os.path.isfile(dsm_prefix + '.pkl'):
        return io_utils.load(dsm_prefix + '.pkl')

    # Load the multiple files: npz for the matrix and pkl for the other data members of Space
    if os.path.isfile(dsm_prefix + '.npz'):
        with np.load(dsm_prefix + '.npz') as loader:
            coo = coo_matrix((loader['data'], (loader['row'], loader['col'])), shape=loader['shape'])

        cooccurrence_matrix = SparseMatrix(csr_matrix(coo))

        with open(dsm_prefix + '_row2id.pkl', 'rb') as f_in:
            row2id = pickle.load(f_in)

        with open(dsm_prefix + '_id2row.pkl', 'rb') as f_in:
            id2row = pickle.load(f_in)

        with open(dsm_prefix + '_column2id.pkl', 'rb') as f_in:
            column2id = pickle.load(f_in)

        with open(dsm_prefix + '_id2column.pkl', 'rb') as f_in:
            id2column = pickle.load(f_in)

        return Space(cooccurrence_matrix, id2row, id2column, row2id=row2id, column2id=column2id)

    if os.path.isfile(dsm_prefix + '.tsv'):
        values = np.loadtxt(dsm_prefix + '.tsv', dtype=float, delimiter='\t', skiprows=0, comments=None, encoding='utf-8')
        targets = np.loadtxt(dsm_prefix + '.rows', dtype=str, skiprows=0, comments=None, encoding='utf-8')
        # Convert to space in sparse matrix format        
        return Space(SparseMatrix(values), list(targets), [])
    
    # If everything fails try to load it as single w2v file
    space_array = np.loadtxt(dsm_prefix + '.w2v', dtype=object, delimiter=' ', skiprows=1, comments=None, encoding='utf-8')
    targets = space_array[:,0].flatten()
    values = space_array[:,1:].astype(np.float)
    # Convert to space and sparse matrix format        
    return Space(SparseMatrix(values), list(targets), [])

