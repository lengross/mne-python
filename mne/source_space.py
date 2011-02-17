# Authors: Alexandre Gramfort <gramfort@nmr.mgh.harvard.edu>
#          Matti Hamalainen <msh@nmr.mgh.harvard.edu>
#
# License: BSD (3-clause)

from math import sqrt
import numpy as np

from .fiff.constants import FIFF
from .fiff.tree import dir_tree_find
from .fiff.tag import find_tag
from .fiff.open import fiff_open


def patch_info(nearest):
    """Patch information in a source space

    Generate the patch information from the 'nearest' vector in
    a source space

    Parameters
    ----------
    nearest: array
        XXX ?

    Returns
    -------
    pinfo: list
        XXX ?
    """
    if nearest is None:
        pinfo = None
        return pinfo

    indn = np.argsort(nearest)
    nearest_sorted = nearest[indn]

    uniq, firsti = np.unique(nearest_sorted, return_index=True)
    uniq, lasti = np.unique(nearest_sorted[::-1], return_index=True)
    lasti = nearest.size - lasti

    pinfo = list()
    for k in range(len(uniq)):
        pinfo.append(indn[firsti[k]:lasti[k]])

    return pinfo


def read_source_spaces(source, add_geom=False, tree=None):
    """Read the source spaces from a FIF file

    Parameters
    ----------
    source: string or file
        The name of the file or an open file descriptor

    add_geom: bool, optional (default False)
        Add geometry information to the surfaces

    tree: dict
        The FIF tree structure if source is a file id.

    Returns
    -------
    src: list
        The list of source spaces
    """
    #   Open the file, create directory
    if isinstance(source, str):
        fid, tree, _ = fiff_open(source)
        open_here = True
    else:
        fid = source
        open_here = False

    #   Find all source spaces
    spaces = dir_tree_find(tree, FIFF.FIFFB_MNE_SOURCE_SPACE)
    if len(spaces) == 0:
        if open_here:
            fid.close()
        raise ValueError, 'No source spaces found'

    src = list()
    for s in spaces:
        print '\tReading a source space...',
        this = _read_one_source_space(fid, s, open_here)
        print '[done]'
        if add_geom:
            complete_source_space_info(this)

        src.append(this)

    print '\t%d source spaces read' % len(spaces)

    if open_here:
        fid.close()

    return src


def _read_one_source_space(fid, this, open_here):
    """Read one source space
    """
    FIFF_BEM_SURF_NTRI = 3104
    FIFF_BEM_SURF_TRIANGLES = 3106

    res = dict()

    tag = find_tag(fid, this, FIFF.FIFF_MNE_SOURCE_SPACE_ID)
    if tag is None:
        res['id'] = int(FIFF.FIFFV_MNE_SURF_UNKNOWN)
    else:
        res['id'] = int(tag.data)

    tag = find_tag(fid, this, FIFF.FIFF_MNE_SOURCE_SPACE_NPOINTS)
    if tag is None:
        if open_here:
            fid.close()
            raise ValueError, 'Number of vertices not found'

    res['np'] = tag.data

    tag = find_tag(fid, this, FIFF_BEM_SURF_NTRI)
    if tag is None:
        tag = find_tag(fid, this, FIFF.FIFF_MNE_SOURCE_SPACE_NTRI)
        if tag is None:
            res['ntri'] = 0
        else:
            res['ntri'] = int(tag.data)
    else:
        res['ntri'] = tag.data

    tag = find_tag(fid, this, FIFF.FIFF_MNE_COORD_FRAME)
    if tag is None:
        if open_here:
            fid.close()
            raise ValueError, 'Coordinate frame information not found'

    res['coord_frame'] = tag.data

    #   Vertices, normals, and triangles
    tag = find_tag(fid, this, FIFF.FIFF_MNE_SOURCE_SPACE_POINTS)
    if tag is None:
        if open_here:
            fid.close()
        raise ValueError, 'Vertex data not found'

    res['rr'] = tag.data.astype(np.float) # make it double precision for mayavi
    if res['rr'].shape[0] != res['np']:
        if open_here:
            fid.close()
        raise ValueError, 'Vertex information is incorrect'

    tag = find_tag(fid, this, FIFF.FIFF_MNE_SOURCE_SPACE_NORMALS)
    if tag is None:
        if open_here:
            fid.close()
        raise ValueError, 'Vertex normals not found'

    res['nn'] = tag.data
    if res['nn'].shape[0] != res['np']:
        if open_here:
            fid.close()
        raise ValueError, 'Vertex normal information is incorrect'

    if res['ntri'] > 0:
        tag = find_tag(fid, this, FIFF_BEM_SURF_TRIANGLES)
        if tag is None:
            tag = find_tag(fid, this, FIFF.FIFF_MNE_SOURCE_SPACE_TRIANGLES)
            if tag is None:
                if open_here:
                    fid.close()
                raise ValueError, 'Triangulation not found'
            else:
                res['tris'] = tag.data
        else:
            res['tris'] = tag.data

        if res['tris'].shape[0] != res['ntri']:
            if open_here:
                fid.close()
            raise ValueError, 'Triangulation information is incorrect'
        else:
            res['tris'] = None

    #   Which vertices are active
    tag = find_tag(fid, this, FIFF.FIFF_MNE_SOURCE_SPACE_NUSE)
    if tag is None:
        res['nuse'] = 0
        res['inuse'] = np.zeros(res['nuse'], dtype=np.int)
        res['vertno'] = None
    else:
        res['nuse'] = tag.data
        tag = find_tag(fid, this, FIFF.FIFF_MNE_SOURCE_SPACE_SELECTION)
        if tag is None:
            if open_here:
                fid.close()
            raise ValueError, 'Source selection information missing'

        res['inuse'] = tag.data.astype(np.int).T
        if len(res['inuse']) != res['np']:
            if open_here:
                fid.close()
            raise ValueError, 'Incorrect number of entries in source space ' \
                              'selection'

        res['vertno'] = np.where(res['inuse'])[0]

    #   Use triangulation
    tag1 = find_tag(fid, this, FIFF.FIFF_MNE_SOURCE_SPACE_NUSE_TRI)
    tag2 = find_tag(fid, this, FIFF.FIFF_MNE_SOURCE_SPACE_USE_TRIANGLES)
    if tag1 is None or tag2 is None:
        res['nuse_tri'] = 0
        res['use_tris'] = None
    else:
        res['nuse_tri'] = tag1.data
        res['use_tris'] = tag2.data - 1 # index start at 0 in Python

    #   Patch-related information
    tag1 = find_tag(fid, this, FIFF.FIFF_MNE_SOURCE_SPACE_NEAREST)
    tag2 = find_tag(fid, this, FIFF.FIFF_MNE_SOURCE_SPACE_NEAREST_DIST)

    if tag1 is None or tag2 is None:
        res['nearest'] = None
        res['nearest_dist'] = None
    else:
        res['nearest'] = tag1.data
        res['nearest_dist'] = tag2.data.T

    res['pinfo'] = patch_info(res['nearest'])
    if res['pinfo'] is not None:
        print 'Patch information added...'

    return res


def complete_source_space_info(this):
    """Add more info on surface
    """
    #   Main triangulation
    print '\tCompleting triangulation info...'
    this['tri_area'] = np.zeros(this['ntri'])
    r1 = this['rr'][this['tris'][:, 0], :]
    r2 = this['rr'][this['tris'][:, 1], :]
    r3 = this['rr'][this['tris'][:, 2], :]
    this['tri_cent'] = (r1 + r2 + r3) / 3.0
    this['tri_nn'] = np.cross((r2-r1), (r3-r1))

    for p in range(this['ntri']): # XXX : can do better
        size = sqrt(np.sum(this['tri_nn'][p,:] * this['tri_nn'][p,:]))
        this['tri_area'][p] = size / 2.0
        this['tri_nn'][p,:] = this['tri_nn'][p,:] / size

    print '[done]'

    #   Selected triangles
    print '\tCompleting selection triangulation info...'
    if this['nuse_tri'] > 0:
        r1 = this['rr'][this['use_tris'][:, 0],:]
        r2 = this['rr'][this['use_tris'][:, 1],:]
        r3 = this['rr'][this['use_tris'][:, 2],:]
        this['use_tri_cent'] = (r1 + r2 + r3) / 3.0
        this['use_tri_nn'] = np.cross((r2-r1), (r3-r1))
        for p in range(this['nuse_tri']): # XXX can do better
            this['use_tri_area'][p] = sqrt(np.sum(this['use_tri_nn'][p,:]
                                           * this['use_tri_nn'][p,:])) / 2.0

    print '[done]'


def find_source_space_hemi(src):
    """Return the hemisphere id for a source space

    Parameters
    ----------
    src: dict
        The source space to investigate

    Returns
    -------
    hemi: int
        Deduced hemisphere id
    """
    xave = src['rr'][:, 0].sum()

    if xave < 0:
        hemi = int(FIFF.FIFFV_MNE_SURF_LEFT_HEMI)
    else:
        hemi = int(FIFF.FIFFV_MNE_SURF_RIGHT_HEMI)

    return hemi
