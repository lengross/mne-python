from . import Raw, pick_types
from . constants import BTI
from . import FIFF

import os
import os.path as op
import struct
import time

from datetime import datetime
from itertools import count
from math import floor

import numpy as np

from .. import verbose

import logging
logger = logging.getLogger('mne')


FIFF_INFO_CHS_FIELDS = ('loc', 'ch_name', 'unit_mul', 'coil_trans',
    'coord_frame', 'coil_type', 'range', 'unit', 'cal', 'eeg_loc',
    'scanno', 'kind', 'logno')

FIFF_INFO_CHS_DEFAULTS = (np.array([0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1],
                          dtype=np.float32), None, 0, None, 0, 0, 1.0,
                          107, 1.0, None, None, 402, None)

FIFF_INFO_DIG_FIELDS = ("kind", "ident", "r", "coord_frame")
FIFF_INFO_DIG_DEFAULTS = (None, None, None, FIFF.FIFFV_COORD_HEAD)

dtypes = zip(range(1, 5), ('i2', 'i4', 'f4', 'f8'))
DTYPES = dict((i, np.dtype(t)) for i, t in dtypes)

###############################################################################
# Reading


def _unpack_matrix(fid, format, rows, cols, dtype):
    """ Aux Function """
    out = np.zeros([rows, cols], dtype=dtype)
    bsize = struct.calcsize(format)
    string = os.read(fid, bsize) if isinstance(fid, int) else fid.read(bsize)
    data = struct.unpack(format, string)
    iter_mat = [(r, c) for r in xrange(rows) for c in xrange(cols)]
    for idx, (row, col) in enumerate(iter_mat):
        out[row, col] = data[idx]

    return out


def _unpack_simple(fid, format, count):
    """ Aux Function """
    bsize = struct.calcsize(format)
    string = os.read(fid, bsize) if isinstance(fid, int) else fid.read(bsize)
    data = list(struct.unpack(format, string))

    return data[0] if count < 2 else list(data)


def bti_read_str(fid, count=1):
    """ Read string """
    format = '>' + ('c' * count)
    data = list(struct.unpack(format, fid.read(struct.calcsize(format))))

    return ''.join(data[0:data.index('\x00') if '\x00' in data else count])


def bti_read_char(fid, count=1):
    " Read character from bti file """

    return _unpack_simple(fid, '>' + ('c' * count), count)


def bti_read_bool(fid, count=1):
    """ Read bool value from bti file """

    return _unpack_simple(fid, '>' + ('?' * count), count)


def bti_read_uint8(fid, count=1):
    """ Read unsigned 8bit integer from bti file """

    return _unpack_simple(fid, '>' + ('B' * count), count)


def bti_read_int8(fid, count=1):
    """ Read 8bit integer from bti file """

    return _unpack_simple(fid, '>' + ('b' * count),  count)


def bti_read_uint16(fid, count=1):
    """ Read unsigned 16bit integer from bti file """

    return _unpack_simple(fid, '>' + ('H' * count), count)


def bti_read_int16(fid, count=1):
    """ Read 16bit integer from bti file """

    return _unpack_simple(fid, '>' + ('H' * count),  count)


def bti_read_uint32(fid, count=1):
    """ Read unsigned 32bit integer from bti file """

    return _unpack_simple(fid, '>' + ('I' * count), count)


def bti_read_int32(fid, count=1):
    """ Read 32bit integer from bti file """

    return _unpack_simple(fid, '>' + ('i' * count), count)


def bti_read_uint64(fid, count=1):
    """ Read unsigned 64bit integer from bti file """

    return _unpack_simple(fid, '>' + ('Q' * count), count)


def bti_read_int64(fid, count=1):
    """ Read 64bit integer from bti file """

    return _unpack_simple(fid, '>' + ('q' * count), count)


def bti_read_float(fid, count=1):
    """ Read 32bit float from bti file """

    return _unpack_simple(fid, '>' + ('f' * count), count)


def bti_read_double(fid, count=1):
    """ Read 64bit float from bti file """

    return _unpack_simple(fid, '>' + ('d' * count), count)


def bti_read_int16_matrix(fid, rows, cols):
    """ Read 16bit integer matrix from bti file """

    format = '>' + ('h' * rows * cols)

    return _unpack_matrix(fid, format, rows, cols, np.int16)


def bti_read_float_matrix(fid, rows, cols):
    """ Read 32bit float matrix from bti file """

    format = '>' + ('f' * rows * cols)
    return _unpack_matrix(fid, format, rows, cols, 'f4')


def bti_read_double_matrix(fid, rows, cols):
    """ Read 64bit float matrix from bti file """

    format = '>' + ('d' * rows * cols)

    return _unpack_matrix(fid, format, rows, cols, 'f8')


def bti_read_transform(fid, rows):
    """ Read 64bit float matrix transform from bti file """

    format = '>' + ('d' * 4 * 4)

    return _unpack_matrix(fid, format, 4, 4, 'f8')


###############################################################################
# Transforms

def _get_m_to_nm(adjust=None, translation=(0.0, 0.02, 0.11)):
    """ Get the general Magnes3600WH to Neuromag coordinate transform

    Parameters
    ----------
    adjust : int | None
        Degrees to tilt x-axis for sensor frame misalignment.
        If None, no adjustment will be applied.
    translation : array-like
        The translation to place the origin of coordinate system
        to the center of the head.

    Returns
    -------
    m_nm_t : ndarray
        4 x 4 rotation, translation, scaling matrix.

    """
    flip_t = np.array(BTI.T_ROT_VV, np.float64)
    adjust_t = np.array(BTI.T_IDENT, np.float64)
    adjust = 0 if adjust is None else adjust
    deg = np.deg2rad(float(adjust))
    adjust_t[[1, 2], [1, 2]] = np.cos(deg)
    adjust_t[[1, 2], [2, 1]] = -np.sin(deg), np.sin(deg)
    m_nm_t = np.ones([4, 4])
    m_nm_t[BTI.T_ROT_IX] = np.dot(flip_t[BTI.T_ROT_IX],
                                  adjust_t[BTI.T_ROT_IX])
    m_nm_t[BTI.T_TRANS_IX] = np.matrix(translation).T

    return m_nm_t


def _read_system_trans(fname):
    """ Read global 4-D system transform
    """
    trans = [l.strip().split(', ') for l in open(fname) if l.startswith(' ')]
    return np.array(trans, dtype=float).reshape([4, 4])


def _m_to_nm_coil_trans(ch_t, bti_t, nm_t, nm_default_scale=True):
    """ transforms 4D coil position to fiff / Neuromag
    """
    ch_t = np.array(ch_t.split(', '), dtype=float).reshape([4, 4])

    nm_coil_trans = _apply_t(_inverse_t(ch_t, bti_t), nm_t)

    if nm_default_scale:
        nm_coil_trans[3, :3] = 0.

    return nm_coil_trans


def _inverse_t(x, t, rot=BTI.T_ROT_IX, trans=BTI.T_TRANS_IX,
               scal=BTI.T_SCA_IX):
    """ Apply inverse transform
    """
    x = x.copy()
    x[scal] *= t[scal]
    x[rot] = np.dot(t[rot].T, x[rot])
    x[trans] -= t[trans]
    x[trans] = np.dot(t[rot].T, x[trans])

    return x


def _apply_t(x, t, rot=BTI.T_ROT_IX, trans=BTI.T_TRANS_IX, scal=BTI.T_SCA_IX):
    """ Apply transform
    """
    x = x.copy()
    x[rot] = np.dot(t[rot], x[rot])
    x[trans] = np.dot(t[rot], x[trans])
    x[trans] += t[trans]
    x[scal] *= t[scal]

    return x


def _merge_t(t1, t2):
    """ Merge two transforms """
    t = np.array(BTI.T_IDENT, dtype=np.float32)
    t[BTI.T_ROT_IX] = np.dot(t1[BTI.T_ROT_IX], t2[BTI.T_ROT_IX])
    t[BTI.T_TRANS_IX] = np.dot(t1[BTI.T_ROT_IX], t2[BTI.T_TRANS_IX])
    t[BTI.T_TRANS_IX] += t1[BTI.T_TRANS_IX]

    return t


def _rename_channels(names):
    """Renames appropriately ordered list of channel names

    Parameters
    ----------
    names : list of str
        Lists of 4-D channel names in ascending order

    Returns
    -------
    generator object :
        Generator object for iteration over MEG channels with Neuromag names.
    """
    ref_mag, ref_grad, eog, ext = ((lambda: count(1))() for i in range(4))
    for i, name in enumerate(names, 1):
        if name.startswith('A'):
            name = 'MEG %3.3d' % i
        elif name == 'RESPONSE':
            name = 'SRI 013'
        elif name == 'TRIGGER':
            name = 'STI 014'
        elif name.startswith('EOG'):
            name = 'EOG %3.3d' % eog.next()
        elif name == 'ECG':
            name = 'ECG 001'
        elif name == 'UACurrent':
            name = 'UTL 001'
        elif name.startswith('M'):
            name = 'RFM %3.3d' % ref_mag.next()
        elif name.startswith('G'):
            name = 'RFG %3.3d' % ref_grad.next()
        elif name.startswith('X'):
            name = 'EXT %3.3d' % ext.next()

        yield name


def convert_head_shape(idx_points, dig_points, use_hpi=False):
    """ Read digitation points from MagnesWH3600 and transform to Neuromag
        coordinates.

    Parameters
    ----------
    idx_points : ndarray
        The index points.
    dix_points : ndarray
        The digitization points.
    use_hpi : bool
        Whether to treat hpi coils as digitization points or not. If False,
        Hpi coils will be discarded.

    Returns
    -------
    dig : list
        A list of dictionaries including the dig points and additional info
    t : ndarray
        The 4 x 4 matrix describing the Magnes3600WH head to Neuromag head
        transformation.
    """

    fp = idx_points  # fiducial points
    dp = np.sum(fp[2] * (fp[0] - fp[1]))
    tmp1, tmp2 = np.sum(fp[2] ** 2), np.sum((fp[0] - fp[1]) ** 2)
    dcos = -dp / np.sqrt(tmp1 * tmp2)
    dsin = np.sqrt(1. - dcos * dcos)
    dt = dp / np.sqrt(tmp2)

    fiducials_nm = np.ones([len(fp), 3])

    for idx, f in enumerate(fp):
        fiducials_nm[idx, 0] = dcos * f[0] - dsin * f[1] + dt
        fiducials_nm[idx, 1] = dsin * f[0] + dcos * f[1]
        fiducials_nm[idx, 2] = f[2]

    # adjust order of fiducials to Neuromag
    fiducials_nm[[1, 2]] = fiducials_nm[[2, 1]]

    t = np.array(BTI.T_IDENT, dtype=np.float32)
    t[0, 0] = dcos
    t[0, 1] = -dsin
    t[1, 0] = dsin
    t[1, 1] = dcos
    t[0, 3] = dt

    dpnts = dig_points
    dig_points_nm = np.dot(t[BTI.T_ROT_IX], dpnts).T
    dig_points_nm += t[BTI.T_TRANS_IX].T

    all_points = np.r_[fiducials_nm, dig_points_nm]
    fiducials_idents = range(1, 4) + range(1, (len(fp) + 1) - 3)
    dig = []
    for idx in xrange(all_points.shape[0]):
        point_info = dict((k, v) for k, v in zip(FIFF_INFO_DIG_FIELDS,
                          FIFF_INFO_DIG_DEFAULTS))
        point_info['r'] = all_points[idx]
        if idx < 3:
            point_info['kind'] = FIFF.FIFFV_POINT_CARDINAL
            point_info['ident'] = fiducials_idents[idx]
        if 2 < idx < len(idx_points) and use_hpi:
            point_info['kind'] = FIFF.FIFFV_POINT_HPI
            point_info['ident'] = fiducials_idents[idx]
        elif idx > 4:
            point_info['kind'] = FIFF.FIFFV_POINT_EXTRA
            point_info['ident'] = (idx + 1) - len(fiducials_idents)

        if 2 < idx < len(idx_points) and not use_hpi:
            pass
        else:
            dig.append(point_info)

    return dig, t


###############################################################################
# Read files

def read_head_shape(fname):
    """Read index points and dig points from BTi head shape file

    Parameters
    ----------
    fname : str
        The absolute path to the headshape file

    Returns
    -------
    idx_points : ndarray
        The index or fiducial points.
    dig_points : ndarray
        The digitazation points.
    """
    with open(fname, 'rb') as fid:
        fid.seek(BTI.FILE_HS_N_DIGPOINTS)
        _n_dig_points = bti_read_int32(fid)
        idx_points = bti_read_double_matrix(fid, BTI.DATA_N_IDX_POINTS, 3)
        dig_points = bti_read_double_matrix(fid, _n_dig_points, 3)

    return idx_points, dig_points


def read_data(fname):
    """Read BTi PDF file

    Parameters
    ----------
    fname : str
        The absolute path to the processed data file (PDF)

    Returns
    -------
    header : dict
        The measurement info.
    data : ndarray
        The channels X time slices MEG measurments.

    """
    pass


def _correct_offset(fid):
    """Compensate offset padding"""
    current = fid.tell()
    fid.seek(0, os.SEEK_CUR)
    if ((current % BTI.FILE_CURPOS) != 0):
        offset = current % BTI.FILE_CURPOS
        fid.seek(BTI.FILE_CURPOS - (offset), os.SEEK_CUR)


def _read_bti_header(fid):
    """ Read bti PDF header
    """
    fid.seek(BTI.FILE_END, os.SEEK_END)
    ftr_pos = fid.tell()
    hdr_pos = bti_read_int64(fid)
    test_val = hdr_pos & BTI.FILE_MASK

    if ((ftr_pos + BTI.FILE_CURPOS - test_val) <= BTI.FILE_MASK):
        hdr_pos = test_val

    if ((hdr_pos % BTI.FILE_CURPOS) != 0):
        hdr_pos += (BTI.FILE_CURPOS - (hdr_pos % BTI.FILE_CURPOS))

    fid.seek(hdr_pos, os.SEEK_SET)

    hdr_size = ftr_pos - hdr_pos

    out = dict(version=bti_read_int16(fid),
               file_type=bti_read_str(fid, BTI.FILE_PDF_H_FTYPE))

    fid.seek(BTI.FILE_PDF_H_ENTER, os.SEEK_CUR)

    out.update(dict(data_format=bti_read_int16(fid),
                acq_mode=bti_read_int16(fid),
                total_epochs=bti_read_int32(fid),
                input_epochs=bti_read_int32(fid),
                total_events=bti_read_int32(fid),
                total_fixed_events=bti_read_int32(fid),
                sample_period=bti_read_float(fid),
                xaxis_label=bti_read_str(fid, BTI.FILE_PDF_H_XLABEL),
                total_processes=bti_read_int32(fid),
                total_chans=bti_read_int16(fid)))

    fid.seek(BTI.FILE_PDF_H_NEXT, os.SEEK_CUR)
    out.update(dict(checksum=bti_read_int32(fid),
                total_ed_classes=bti_read_int32(fid),
                total_associated_files=bti_read_int16(fid),
                last_file_index=bti_read_int16(fid),
                timestamp=bti_read_int32(fid)))

    fid.seek(BTI.FILE_PDF_H_EXIT, os.SEEK_CUR)

    _correct_offset(fid)

    return out, hdr_size, ftr_pos


def _read_bti_epoch(fid):
    """Read BTi epoch"""
    out = dict(pts_in_epoch=bti_read_int32(fid),
                epoch_duration=bti_read_float(fid),
                expected_iti=bti_read_float(fid),
                actual_iti=bti_read_float(fid),
                total_var_events=bti_read_int32(fid),
                checksum=bti_read_int32(fid),
                epoch_timestamp=bti_read_int32(fid))

    fid.seek(BTI.FILE_PDF_EPOCH_EXIT, os.SEEK_CUR)

    return out


def _read_channel(fid):
    """Read BTi PDF channel"""
    out = dict(chan_label=bti_read_str(fid, BTI.FILE_PDF_CH_LABELSIZE),
                chan_no=bti_read_int16(fid),
                attributes=bti_read_int16(fid),
                scale=bti_read_float(fid),
                yaxis_label=bti_read_str(fid, BTI.FILE_PDF_CH_YLABEL),
                valid_min_max=bti_read_int16(fid))

    fid.seek(BTI.FILE_PDF_CH_NEXT, os.SEEK_CUR)

    out.update(dict(ymin=bti_read_double(fid),
                ymax=bti_read_double(fid),
                index=bti_read_int32(fid),
                checksum=bti_read_int32(fid),
                off_flag=bti_read_str(fid, BTI.FILE_PDF_CH_OFF_FLAG),
                offset=bti_read_float(fid)))

    fid.seek(BTI.FILE_PDF_CH_EXIT, os.SEEK_CUR)

    return out


def _read_event(fid):
    """Read BTi PDF event"""
    out = dict(event_name=bti_read_str(fid, BTI.FILE_PDF_EVENT_NAME),
                start_lat=bti_read_float(fid),
                end_lat=bti_read_float(fid),
                step_size=bti_read_float(fid),
                fixed_event=bti_read_int16(fid),
                checksum=bti_read_int32(fid))

    fid.seek(BTI.FILE_PDF_EVENT_EXIT, os.SEEK_CUR)
    _correct_offset(fid)

    return out


def _read_process(fid):
    """Read BTi PDF process"""

    out = dict(nbytes=bti_read_int32(fid),
                blocktype=bti_read_str(fid, BTI.FILE_PDF_PROCESS_BLOCKTYPE),
                checksum=bti_read_int32(fid),
                user=bti_read_str(fid, BTI.FILE_PDF_PROCESS_USER),
                timestamp=bti_read_int32(fid),
                filename=bti_read_str(fid, BTI.FILE_PDF_PROCESS_FNAME),
                total_steps=bti_read_int32(fid))

    fid.seek(BTI.FILE_PDF_PROCESS_EXIT, os.SEEK_CUR)

    _correct_offset(fid)

    return out


def _read_assoc_file(fid):
    """Read BTi PDF assocfile"""

    out = dict(file_id=bti_read_int16(fid),
                length=bti_read_int16(fid))

    fid.seek(BTI.FILE_PDF_ASSOC_NEXT, os.SEEK_CUR)
    out['checksum'] = bti_read_int32(fid)

    return out


def _read_pfid_ed(fid):
    """Read PDF ed file"""

    out = dict(comment_size=bti_read_int32(fid),
             name=bti_read_str(fid, BTI.FILE_PDFED_NAME))

    fid.seek(BTI.FILE_PDFED_NEXT, os.SEEK_CUR)
    out.update(dict(pdf_number=bti_read_int16(fid),
                    total_events=bti_read_int32(fid),
                    timestamp=bti_read_int32(fid),
                    flags=bti_read_int32(fid),
                    de_process=bti_read_int32(fid),
                    checksum=bti_read_int32(fid),
                    ed_id=bti_read_int32(fid),
                    win_width=bti_read_float(fid),
                    win_offset=bti_read_float(fid)))

    fid.seek(BTI.FILE_PDFED_NEXT, os.SEEK_CUR)

    return out


def _read_userblock(fid, blocks):
    """ Read user block from config """

    block = dict()
    block['hdr'] = dict(
         nbytes=bti_read_int32(fid),
         kind=bti_read_str(fid, BTI.FILE_CONF_UBLOCK_TYPE),
         checksum=bti_read_int32(fid),
         username=bti_read_str(fid, BTI.FILE_CONF_UBLOCK_UNAME),
         timestamp=bti_read_int32(fid),
         user_space_size=bti_read_int32(fid),
         reserved=bti_read_char(fid, BTI.FILE_CONF_UBLOCK_RESERVED))

    kind, data = block['hdr']['kind'], dict()
    if kind in [k for k in BTI if k[:6] == 'UBLOCK']:
        if kind == BTI.FILE_CONF_UBLOCK_MAG_INFO:
            data['version'] = bti_read_int32(fid)
            fid.seek(BTI.FILE_CONF_UBLOCK_PADDING, os.SEEK_CUR)
            data['headers'] = list()
            for i in xrange(BTI.FILE_CONF_UBLOCK_BHRANGE):
                d = dict(name=bti_read_str(fid, BTI.FILE_UBLOCK_BHNAME),
                         transform=bti_read_transform(fid),
                         units_per_bit=bti_read_float(fid))
                data['headers'] += [d]

        elif kind == BTI.UBLOCK_COH_PNTS:
            data['num_points'] = bti_read_int32(fid)
            data['status'] = bti_read_int32(fid)
            data['points'] = []
            for i in xrange(BTI.UBLOCK_PRANGE):
                d = dict(pos=bti_read_double_matrix(fid, 1, 3),
                         direction=bti_read_double_matrix(fid, 1, 3),
                         error=bti_read_double(fid))
                data['points'] += [d]

        elif kind == BTI.UBLOCK_CCP_XFM:
            data['method'] = bti_read_int32(fid)
            fid.seek(BTI.FILE_CONF_UBLOCK_XFM, os.SEEK_CUR)
            data['transform'] = bti_read_transform(fid)

        elif kind == BTI.UBLOCK_EEG_LOCS:
            data['electrodes'] = []
            while True:
                if e.label == BTI.FILE_CONF_UBLOCK_ELABEL_END:
                    break
                d = dict(label=bti_read_str(fid, BTI.FILE_CONF_UBLOCK_ELABEL),
                          location=bti_read_double_matrix(fid, 1, 3))
                data['electrodes'] += [d]

        elif kind in [BTI.UBLOCK_WHC_CHAN_MAP_VER, BTI.UBLOCK_WHS_SUBS_VER]:
            data['version'] = bti_read_int16(fid)
            data['struct_size'] = bti_read_int16(fid)
            data['entries'] = bti_read_int16(fid)
            fid.seek(BTI.FILE_CONF_UBLOCK_SVERS, os.SEEK_CUR)

        elif kind == BTI.UBLOCK_WHC_CHAN_MAP:
            num_channels = None
            for block in blocks:
                if block['hdr']['kind'] == BTI.UBLOCK_WHC_CHAN_MAP_VER:
                    num_channels = block['data']['entries']
                    break

            if num_channels is None:
                raise ValueError('Cannot find block %s to determine number'
                                 'of channels' % BTI.UBLOCK_WHC_CHAN_MAP_VER)

            data['channels'] = list()
            for i in xrange(num_channels):
                d = dict(subsys_type=bti_read_int16(fid),
                         subsys_num=bti_read_int16(fid),
                         card_num=bti_read_int16(fid),
                         chan_num=bti_read_int16(fid),
                         recdspnum=bta_read_int16(fid))
                d += [d]

        elif kind == BTI.UBLOCK_WHS_SUBS:
            num_subsys = None
            for block in blocks:
                if block['hdr']['kind'] == BTI.UBLOCK_WHS_SUBS_VER:
                    num_subsys = block['data']['entries']
                    break

            if num_subsys is None:
                raise ValueError('Cannot find block %s to determine number o'
                                 'f subsystems' % BTI.UBLOCK_WHS_SUBS_VER)

            data['subsys'] = list()
            for sub_key in range(num_subsys):
                d = dict(subsys_type=bti_read_int16(fid),
                        subsys_num=bti_read_int16(fid),
                        cards_per_sys=bti_read_int16(fid),
                        channels_per_card=bti_read_int16(fid),
                        card_version=bti_read_int16(fid))
                fid.seek(BTI.FILE_CONF_UBLOCK_PADDING, os.SEEK_CUR)
                d.update(dict(offsetdacgain=bti_read_float(fid),
                        squid_type=bti_read_int32(fid),
                        timesliceoffset=bti_read_int16(fid),
                        padding=bti_read_int16(fid),
                        volts_per_bit=bti_read_float(fid)))
                data['subkeys'] += [d]

        elif kind == BTI.UBLOCK_CH_LABEL:
            data['version'] = bti_read_int32(fid)
            data['entries'] = bti_read_int32(fid)
            fid.seek(BTI.FILE_CONF_UBLOCK_CH_PADDING, os.SEEK_CUR)

            data['labels'] = list()
            for label in xrange(data['entries']):
                += [bti_read_str(fid, BTI.FILE_CONF_UBLOCK_CH_LABEL)]

        elif kind == BTI.UBLOCK_CH_CAL:                                      # 'B_Calibration'
        elif kind == BTI.UBLOCK_SYS_CONF:                                    # 'B_SysConfigTime'
        elif kind == BTI.UBLOCK_SYS_DELT_ENA:                                # 'B_DELTA_ENABLED'
        elif kind == BTI.UBLOCK_ETABLE_USED:                                 # 'B_E_table_used'
        elif kind == BTI.UBLOCK_ETABLE:                                      # 'B_E_TABLE'
        elif kind == BTI.UBLOCK_WEIGHTS_USED:                                # 'B_weights_used'
        elif kind == BTI.UBLOCK_TRIG_MASK:                                   # 'B_trig_mask'
    elif  kind[:4] == BTI.UBLOCK_WEIGHT_TABLE:

    else:


    _correct_offset(fid)

    retun = block


def _read_dev_hdr(fid):
    """ Read device header """
    return dict(size=bti_read_int32(fid),
                checksum=bti_read_int32(fid),
                reserved=bti_read_str(fid, BTI.FILE_CONF_CH_RESERVED))


def _read_coil_def(fid):
    """ Read coil definition """
    coildef = dict(position=bti_read_double_matrix(fid, 1, 3),
                   orientation=bti_read_double_matrix(fid, 1, 3),
                   radius=bti_read_double(fid),
                   wire_radius=bti_read_double(fid),
                   turns=bti_read_int16(fid))
    fid.seek(fid, 2, os.SEEK_CUR)
    coildef['checksum'] = bti_read_int32(fid)
    coildef['reserved'] = bti_read_str(fid, 32)


def _read_ch_config(fid):
    """Read BTi channel config"""

    cfg = dict(name=bti_read_str(fid, BTI.FILE_CONF_CH_NAME),
            chan_no=bti_read_int16(fid),
            ch_type=bti_read_uint16(fid),
            sensor_no=bti_read_int16(fid))

    fid.seek(fid, BTI.FILE_CONF_CH_NEXT, os.SEEK_CUR)

    cfg.update(dict(
            gain=bti_read_float(fid),
            units_per_bit=bti_read_float(fid),
            yaxis_label=bti_read_str(fid, BTI.FILE_CONF_CH_YLABEL),
            aar_val=bti_read_double(fid),
            checksum=bti_read_int32(fid),
            reserved=bti_read_str(fid, BTI.FILE_CONF_CH_RESERVED)))

    _correct_offset(fid)

    # Then the channel info
    ch_type, chan = cfg['ch_type'], dict()
    chan['dev'] = _read_dev_hdr(fid)
    if ch_type in [BTI.CHTYPE_MEG, BTI.CHTYPE_REF]:
        chan['loops'] = [_read_coil_def(fid) for d in
                        range(chan['dev']['total_loops'])]

    elif ch_type == BTI.CHTYPE_EEG:
        chan['impedance'] = bti_read_float(fid)
        chan['padding'] = bti_read_str(fid, BTI.FILE_CONF_CH_PADDING)
        chan['transform'] = bti_read_transform(fid)
        chan['reserved'] = bti_read_char(fid, BTI.FILE_CONF_CH_RESERVED)

    elif ch_type in [BTI.CHTYPE_TRIGGER,  BTI.CHTYPE_EXTERNAL,
                     BTI.CHTYPE_UTILITY, BTI.CHTYPE_DERIVED]:
        chan['user_space_size'] = bti_read_int32(fid)
        if ch_type == BTI.CHTYPE_TRIGGER:
            fid.seek(2, os.SEEK_CUR)
        chan['reserved'] = bti_read_str(fid, BTI.FILE_CONF_CH_RESERVED)

    elif ch_type == BTI.CHTYPE_SHORTED:
        chan['reserved'] = bti_read_str(fid, BTI.FILE_CONF_CH_RESERVED)

    cfg['chan'] = chan

    _correct_offset(fid)

    return cfg


def read_raw_data(info, start=None, stop=None, order='by_name',
                  dtype='f8'):
    """ Read Bti processed data file (PDF)

    Parameters
    ----------
    info : dict
        The measurement info drawn from the BTi processed data file (PDF).
    start : int | None
        The number of the first time slice to read. If None, all data will
        be read from the begninning.
    stop : int | None
        The number of the last time slice to read. If None, all data will
        be read to the end.
    order : index | 'by_name' | None
        The order of the data along the channel axis. If 'by_name',
        data will be returnend sorted by channel names, if None, by
        acquisition order.
    dtype : str | dtype object
        The type the data are casted to.

    Returns
    -------
    data : ndarray
        The measurement data, a channels x timeslices array.
    """
    total_slices = info['total_slices']
    if start is None:
        start = 0
    if stop is None:
        stop = total_slices

    if any([start < 0, stop > total_slices, start >= stop]):
        raise RuntimeError('Invalid data range supplied:'
                           ' %d, %d' % (start, stop))

    info['fid'].seek(info['bytes_per_slice'] * start)

    cnt = (stop - start) * info['total_chans']
    shape = [stop - start, info['total_chans']]
    data = np.fromfile(info['fid'], dtype=info['dtype'],
                       count=cnt).reshape(shape).T.astype(dtype)

    if order == 'by_name':
        mapping = [(i, d['chan_label']) for i, d in
                   enumerate(info['channels'])]
        sort = sorted(mapping, key=lambda c: int(c[1][1:])
                      if c[1][0] == BTI.DATA_MEG_CH_CHAR else c[1])
        order = [idx[0] for idx in sort]

    return data if order is None else data[order]


def read_pdf_info(fname):
    """ Read Bti processed data file (PDF)

    Parameters
    ----------
    fname : str
        The file name of the bti processed data file (PDF)

    Returns
    -------
    info : dict
        The info structure from the BTi PDF header
    """

    with open(fname, 'rb') as fid:

        info, hdr_size, ftr_pos = _read_bti_header(fid)

        info['epochs'] = [_read_bti_epoch(fid) for epoch in
                          xrange(info['total_epochs'])]

        info['channels'] = [_read_channel(fid) for ch in
                            xrange(info['total_chans'])]

        info['events'] = [_read_event(fid) for event in
                          xrange(info['total_events'])]

        info['processes'] = [_read_process(fid) for process in
                             xrange(info['total_processes'])]

        info['assocfiles'] = [_read_assoc_file(fid) for af in
                              xrange(info['total_associated_files'])]

        info['edclasses'] = [_read_pfid_ed(fid) for ed_class in
                             range(info['total_ed_classes'])]

        # We load any remaining data
        fid.seek(0, os.SEEK_CUR)
        info['extradata'] = fid.read(ftr_pos - fid.tell())

        # copy of fid into info
        info['fid'] = os.fdopen(os.dup(fid.fileno()), 'r')

        # calculate n_tsl
        info['total_slices'] = sum(e['pts_in_epoch'] for e in
                                   info['epochs'])

        info['dtype'] = DTYPES[info['data_format']]

        bps = info['dtype'].itemsize * info['total_chans']
        info['bytes_per_slice'] = bps

        return info


def read_config(fname):
    """Read BTi system config file

    Parameters
    ----------
    fname : str
        The absolute path to the config file

    Returns
    -------
    data : ndarray
        The channels X time slices MEG measurments.

    """
    with open(fname, 'rb') as fid:
        cfg = dict(version=bti_read_int16(fid),
                    site_name=bti_read_str(fid, BTI.FILE_CONF_SITENAME),
                    dap_hostname=bti_read_str(fid, BTI.FILE_CONF_HOSTNAME),
                    sys_type=bti_read_int16(fid),
                    sys_options=bti_read_int32(fid),
                    supply_freq=bti_read_int16(fid),
                    total_chans=bti_read_int16(fid),
                    system_fixed_gain=bti_read_float(fid),
                    volts_per_bit=bti_read_float(fid),
                    total_sensors=bti_read_int16(fid),
                    total_user_blocks=bti_read_int16(fid),
                    next_der_chan_no=bti_read_int16(fid))

        fid.seek(fid, BTI.FILE_CONF_NEXT, os.SEEK_CUR)
        cfg['checksum'] = bti_read_uint32(fid)
        cfg['reserved'] = bti_read_char(fid, BTI.FILE_CONF_RESERVED)
        cfg['transforms'] = [bti_read_transform(fid) for xfm in
                             xrange(cfg['hdr']['total_sensors'])]

        cfg['user_blocks'] = [_read_userblock(fid) for block in
                              xrange(cfg['total_user_blocks'])]

        # Finally, the channel information
        cfg['channels'] = [_read_ch_config(fid) for ch in
                           xrange(cfg['total_chans'])]

    return cfg


class RawBTi(Raw):
    """ Raw object from 4-D Neuroimaging MagnesWH3600 data

    Parameters
    ----------
    pdf_fname : str | None
        absolute path to the processed data file (PDF)
    config_fname : str | None
        absolute path to system confnig file. If None, it is assumed to be in
        the same directory.
    head_shape_fname : str
        absolute path to the head shape file. If None, it is assumed to be in
        the same directory.
    rotation_x : float | int | None
        Degrees to tilt x-axis for sensor frame misalignment.
        If None, no adjustment will be applied.
    translation : array-like
        The translation to place the origin of coordinate system
        to the center of the head.
    use_hpi : bool
        Whether to treat hpi coils as digitization points or not. If
        False, HPI coils will be discarded.
    force_units : bool | float
        If True and MEG sensors are scaled to 1, data will be scaled to
        base_units. If float, data will be scaled to the value supplied.
    verbose : bool, str, int, or None
        If not None, override default verbose level (see mne.verbose).

    Attributes & Methods
    --------------------
    See documentation for mne.fiff.Raw

    """
    @verbose
    def __init__(self, pdf_fname, config_fname, head_shape_fname, data=None,
                 rotation_x=2, translation=(0.0, 0.02, 0.11), use_hpi=False,
                 force_units=False, verbose=True):

        logger.info('Opening 4-D header file %s...' % hdr_fname)
        self.hdr = read_bti_ascii(hdr_fname)
        self._root, self._hdr_name = op.split(hdr_fname)
        self._data_file = data_fname
        self.dev_head_t_fname = dev_head_t_fname
        self.head_shape_fname = head_shape_fname
        self.sep = seperator
        self._use_hpi = use_hpi
        self.bti_to_nm = _get_m_to_nm(rotation_x, translation)

        logger.info('Creating Neuromag info structure ...')
        info = self._create_raw_info()

        cals = np.zeros(info['nchan'])
        for k in range(info['nchan']):
            cals[k] = info['chs'][k]['range'] * info['chs'][k]['cal']

        self.verbose = verbose
        self.cals = cals
        self.rawdir = None
        self.proj = None
        self.comp = None
        self.fids = list()
        self._preloaded = True
        self._projector_hashes = [None]
        self.info = info

        logger.info('Reading raw data from %s...' % data_fname)
        # rescale
        self._data = self._read_data() if not data else data
        self.first_samp, self.last_samp = 0, self._data.shape[1] - 1
        assert len(self._data) == len(self.info['ch_names'])
        self._times = np.arange(self.first_samp, \
                                self.last_samp + 1) / info['sfreq']
        self._projectors = [None]
        logger.info('    Range : %d ... %d =  %9.3f ... %9.3f secs' % (
                   self.first_samp, self.last_samp,
                   float(self.first_samp) / info['sfreq'],
                   float(self.last_samp) / info['sfreq']))

        if force_units is not None:
            pick_mag = pick_types(info, meg='mag', eeg=False, misc=False,
                                  eog=False, ecg=False)
            scale = 1e-15 if force_units != True else force_units
            logger.info('    Scaling raw data to %s' % str(scale))
            self._data[pick_mag] *= scale

        # remove subclass helper attributes to create a proper Raw object.
        for attr in self.__dict__:
            if attr not in Raw.__dict__:
                del attr
        logger.info('Ready.')

    @verbose
    def _create_raw_info(self):
        """ Fills list of dicts for initializing empty fiff with 4D data
        """
        info = {}
        sep = self.sep
        d = datetime.strptime(self.hdr[BTI.HDR_DATAFILE]['Session'],
                              '%d' + sep + '%y' + sep + '%m %H:%M')

        sec = time.mktime(d.timetuple())
        info['projs'] = []
        info['comps'] = []
        info['meas_date'] = np.array([sec, 0], dtype=np.int32)
        sfreq = self.hdr[BTI.HDR_FILEINFO]['Sample Frequency'][:-2]
        info['sfreq'] = float(sfreq)
        info['nchan'] = int(self.hdr[BTI.HDR_CH_GROUPS]['CHANNELS'])
        ch_names = _bti_get_channel_names(self.hdr)
        info['ch_names'] = list(_rename_channels(ch_names))
        ch_mapping = zip(ch_names, info['ch_names'])

        sensor_trans = dict((dict(ch_mapping)[k], v) for k, v in
                             self.hdr[BTI.HDR_CH_TRANS].items())
        info['bads'] = []  # TODO

        fspec = info.get(BTI.HDR_DATAFILE, None)
        if fspec is not None:
            fspec = fspec.split(',')[2].split('ord')[0]
            ffreqs = fspec.replace('fwsbp', '').split('-')
        else:
            logger.info('... Cannot find any filter specification' \
                  ' No filter info will be set.')
            ffreqs = 0, 1000

        info['highpass'], info['lowpass'] = ffreqs
        info['acq_pars'], info['acq_stim'] = None, None
        info['filename'] = None
        info['ctf_head_t'] = None
        info['dev_ctf_t'] = []
        info['filenames'] = []
        chs = []

        # get 4-D head_dev_t needed for appropriate
        sensor_coord_frame = FIFF.FIFFV_COORD_DEVICE
        use_identity = False
        if isinstance(self.dev_head_t_fname, str):
            logger.info('... Reading device to head transform from %s.' %
                        self.dev_head_t_fname)
            try:
                bti_sys_trans = _read_system_trans(self.dev_head_t_fname)
            except:
                logger.info('... Could not read headshape data. '
                            'Using identity transform instead')
                use_identity = True
        else:
            logger.info('... No device to head transform specified. '
                        'Using identity transform instead')
            use_identity = True

        if use_identity:
            sensor_coord_frame = FIFF.FIFFV_COORD_HEAD
            bti_sys_trans = np.array(BTI.T_IDENT, np.float32)

        logger.info('... Setting channel info structure.')
        for idx, (chan_4d, chan_vv) in enumerate(ch_mapping, 1):
            chan_info = dict((k, v) for k, v in zip(FIFF_INFO_CHS_FIELDS,
                             FIFF_INFO_CHS_DEFAULTS))
            chan_info['ch_name'] = chan_vv
            chan_info['logno'] = idx
            chan_info['scanno'] = idx

            if any([chan_vv.startswith(k) for k in ('MEG', 'RFG', 'RFM')]):
                t = _m_to_nm_coil_trans(sensor_trans[chan_vv], bti_sys_trans,
                                        self.bti_to_nm)
                chan_info['coil_trans'] = t
                chan_info['loc'] = np.roll(t.copy().T, 1, 0)[:, :3].flatten()
                chan_info['logno'] = idx

            if chan_vv.startswith('MEG'):
                chan_info['kind'] = FIFF.FIFFV_MEG_CH
                chan_info['coil_type'] = FIFF.FIFFV_COIL_MAGNES_MAG
                chan_info['coord_frame'] = sensor_coord_frame
                chan_info['unit'] = FIFF.FIFF_UNIT_T

            elif chan_vv.startswith('RFM'):
                chan_info['kind'] = FIFF.FIFFV_REF_MEG_CH
                chan_info['coil_type'] = FIFF.FIFFV_COIL_MAGNES_R_MAG
                chan_info['coord_frame'] = FIFF.FIFFV_COORD_DEVICE
                chan_info['unit'] = FIFF.FIFF_UNIT_T

            elif chan_vv.startswith('RFG'):
                chan_info['kind'] = FIFF.FIFFV_REF_MEG_CH
                chan_info['coord_frame'] = FIFF.FIFFV_COORD_DEVICE
                chan_info['unit'] = FIFF.FIFF_UNIT_T_M
                if chan_4d in ('GxxA', 'GyyA'):
                    chan_info['coil_type'] = FIFF.FIFFV_COIL_MAGNES_R_GRAD_DIA
                elif chan_4d in ('GyxA', 'GzxA', 'GzyA'):
                    chan_info['coil_type'] = FIFF.FIFFV_COIL_MAGNES_R_GRAD_OFF

            elif chan_vv == 'STI 014':
                chan_info['kind'] = FIFF.FIFFV_STIM_CH
            elif chan_vv.startswith('EOG'):
                chan_info['kind'] = FIFF.FIFFV_EOG_CH
            elif chan_vv == 'ECG 001':
                chan_info['kind'] = FIFF.FIFFV_ECG_CH
            elif chan_vv == 'RSP 001':
                chan_info['kind'] = FIFF.FIFFV_RESP_CH
            elif chan_vv.startswith('EXT'):
                chan_info['kind'] = FIFF.FIFFV_MISC_CH
            elif chan_vv.startswith('UTL'):
                chan_info['kind'] = FIFF.FIFFV_MISC_CH

            chs.append(chan_info)

        info['chs'] = chs
        info['meas_id'] = None
        info['file_id'] = None

        identity = np.array(BTI.T_IDENT, np.float32)
        if self.head_shape_fname is not None:
            logger.info('... Reading digitization points from %s' %
                        self.head_shape_fname)
            info['dig'], m_h_nm_h = read_head_shape(self.head_shape_fname,
                                                     self._use_hpi)
            if m_h_nm_h is None:
                logger.info('Could not read head shape data. '
                           'Sensor data will stay in head coordinate frame')
                nm_dev_head_t = identity
            else:
                nm_to_m_sensor = _inverse_t(identity, self.bti_to_nm)
                nm_sensor_m_head = _merge_t(bti_sys_trans, nm_to_m_sensor)
                nm_dev_head_t = _merge_t(m_h_nm_h, nm_sensor_m_head)
                nm_dev_head_t[3, :3] = 0.
        else:
            logger.info('Warning. No head shape file provided. '
                        'Sensor data will stay in head coordinate frame')
            nm_dev_head_t = identity

        info['dev_head_t'] = {}
        info['dev_head_t']['from'] = FIFF.FIFFV_COORD_DEVICE
        info['dev_head_t']['to'] = FIFF.FIFFV_COORD_HEAD
        info['dev_head_t']['trans'] = nm_dev_head_t

        logger.info('Done.')
        return info

    def _read_data(self, count=-1, dtype=np.float32):
        """ Reads data from binary string file (dumped: time slices x channels)
        """
        _ntsl = self.hdr[BTI.HDR_FILEINFO]['Time slices']
        ntsl = int(_ntsl.replace(' slices', ''))
        cnt, dtp = count, dtype
        with open(self._data_file, 'rb') as f:
            shape = (ntsl, self.info['nchan'])
            data = np.fromfile(f, dtype=dtp, count=cnt)

        return data.reshape(shape).T