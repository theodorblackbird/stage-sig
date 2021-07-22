import numpy as np

from numpy.random import RandomState

from numbers import Number, Integral

from typing import Optional, Union, List, Tuple

ArrayOnCPU = np.ndarray
ArrayOnGPU = np.ndarray
ArrayOnCPUOrGPU = Union[np.ndarray, np.ndarray]

RandomStateOrSeed = Union[Integral, RandomState]

# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# (Type) checkers
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------

def check_positive_value(scalar : Number, name : str) -> Number:
    if scalar <= 0:
        raise ValueError(f'The parameter \'{name}\' should have a positive value.')
    return scalar
    
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# (Batched) computations
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------

def matrix_diag(A : ArrayOnGPU) -> ArrayOnGPU:
    """Takes as input an array of shape (..., d, d) and returns the diagonals along the last two axes with output shape (..., d)."""
    return np.einsum('...ii->...i', A)

def matrix_mult(X : ArrayOnGPU, Y : Optional[ArrayOnGPU] = None, transpose_X : bool = False, transpose_Y : bool = False) -> ArrayOnGPU:
    subscript_X = '...ji' if transpose_X else '...ij'
    subscript_Y = '...kj' if transpose_Y else '...jk'
    return np.einsum(f'{subscript_X},{subscript_Y}->...ik', X, Y if Y is not None else X)
    
def squared_norm(X : ArrayOnGPU, axis : int = -1) -> ArrayOnGPU:
    return np.sum(np.square(X), axis=axis)

def squared_euclid_dist(X : ArrayOnGPU, Y : Optional[ArrayOnGPU] = None) -> ArrayOnGPU:
    X_n2 = squared_norm(X)
    if Y is None:
        D2 = (X_n2[..., :, None] + X_n2[..., None, :]) - 2 * matrix_mult(X, X, transpose_Y=True)
    else:
        Y_n2 = squared_norm(Y, axis=-1)
        D2 = (X_n2[..., :, None] + Y_n2[..., None, :]) - 2 * matrix_mult(X, Y, transpose_Y=True)
    return D2
    
def outer_prod(X : ArrayOnGPU, Y : ArrayOnGPU) -> ArrayOnGPU:
    return np.reshape(X[..., :, None] * Y[..., None, :], X.shape[:-1] + (-1,))
    
def robust_sqrt(X : ArrayOnGPU) -> ArrayOnGPU:
    return np.sqrt(np.maximum(X, 1e-20))
    
def euclid_dist(self, X : ArrayOnGPU, Y : Optional[ArrayOnGPU] = None) -> ArrayOnGPU:
    return robust_sqrt(squared_euclid_dist(X, Y))
    
def robust_nonzero(X : ArrayOnGPU) -> ArrayOnGPU:
    return np.abs(X) > 1e-10
    
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# Probability stuff
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------

def check_random_state(seed : Optional[RandomStateOrSeed] = None) -> RandomState:
    if seed is None or isinstance(seed, Integral):
        return RandomState(seed)
    elif isinstance(seed, RandomState):
        return seed
    raise ValueError(f'{seed} cannot be used to seed a cupy.random.RandomState instance')

def draw_rademacher_matrix(shape : Union[List[int], Tuple[int]], random_state : Optional[RandomStateOrSeed] = None) -> ArrayOnGPU:
    random_state = check_random_state(random_state)
    return np.where(random_state.uniform(size=shape) < 0.5, np.ones(shape), -np.ones(shape))

def draw_bernoulli_matrix(shape : Union[List[int], Tuple[int]], prob : float, random_state : Optional[RandomStateOrSeed] = None) -> ArrayOnGPU:
    random_state = check_random_state(random_state)
    return np.where(random_state.uniform(size=shape) < prob, np.ones(shape), np.zeros(shape))
    
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# Projection stuff
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
    
def subsample_outer_prod_comps(X : ArrayOnGPU, Z : ArrayOnGPU, sampled_idx : Union[ArrayOnGPU, List[int]]) -> Tuple[ArrayOnGPU, ArrayOnGPU]:
    idx_X = np.arange(X.shape[-1]).reshape([-1, 1, 1])
    idx_Z = np.arange(Z.shape[-1]).reshape([1, -1, 1])
    idx_pairs = np.reshape(np.concatenate((idx_X + np.zeros_like(idx_Z), idx_Z + np.zeros_like(idx_X)), axis=-1), (-1, 2))
    sampled_idx_pairs = np.squeeze(np.take(idx_pairs, sampled_idx, axis=0))
    X_proj = np.take(X, sampled_idx_pairs[:, 0], axis=-1)
    Z_proj = np.take(Z, sampled_idx_pairs[:, 1], axis=-1)
    return X_proj, Z_proj

def compute_count_sketch(X : ArrayOnGPU, hash_index : ArrayOnGPU, hash_bit : ArrayOnGPU, n_components : Optional[int] = None) -> ArrayOnGPU:
    # if n_components is None, get it from the hash_index array
    n_components = n_components if n_components is not None else np.max(hash_index)
    hash_mask = np.asarray(hash_index[:, None] == np.arange(n_components)[None, :], dtype=X.dtype)
    X_count_sketch = np.einsum('...i,ij,i->...j', X, hash_mask, hash_bit)
    return X_count_sketch
    
def convolve_count_sketches(X_count_sketch : ArrayOnGPU, Z_count_sketch : ArrayOnGPU) -> ArrayOnGPU:
    X_count_sketch_fft = np.fft.fft(X_count_sketch, axis=-1)
    Z_count_sketch_fft = np.fft.fft(Z_count_sketch, axis=-1)
    XZ_count_sketch = np.real(np.fft.ifft(X_count_sketch_fft * Z_count_sketch_fft, axis=-1))
    return XZ_count_sketch
    
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
