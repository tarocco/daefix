"""
DAEFix

Repairs COLLADA .dae files exported from Cinema 4D so that they are
compatible with Second Life mesh upload.
"""

import re
import os, sys
import io
from argparse import ArgumentParser
import collada
from collada import Collada
from collada.scene import *
from transforms3d.affines import *
from transforms3d.quaternions import *
from math import pi

def parse_joint_tag(tag_str):
    """
    Parses and substitutes id and sid attribute values joint type node
    tags with the name attribute value
    :param tag_str: (string) XML (open) tag string
    :return: (bool, tuple, string) valid parse, attributes
    (type, id, name, sid), repaired tag string
    """
    tag_re = re.compile(r'<node ')
    if tag_re.match(tag_str):
        try:
            type_re = re.compile(r' type="([^"]*)"')
            _type = type_re.search(tag_str).group(1)
            if _type.lower() == 'joint':
                id_re = re.compile(r'(.*) id="([^"]*)"(.*)')
                name_re = re.compile(r'(.*) name="([^"]*)"(.*)')
                sid_re = re.compile(r'(.*) sid="([^"]*)"(.*)')
                _id = id_re.match(tag_str).group(2)
                name = name_re.match(tag_str).group(2)
                sid = sid_re.match(tag_str).group(2)
                repaired = tag_str
                repaired = id_re.sub(rf'\g<1> id="{name}"\g<3>',
                                     repaired)
                repaired = sid_re.sub(rf'\g<1> sid="{name}"\g<3>',
                                      repaired)
                return True, (_type, _id, name, sid), repaired
        except:
            pass
    return False, None, None


def parse_name_array_tag(tag_str, contents, lut):
    """
    Parses and replaces name_array tag values by
    a lookup table (LUT)
    :param tag_str:
    :param contents:
    :param lut: (dict) lookup table mapping SID to name attributes
    :return: (bool, string) valid parse, repaired contents
    """
    tag_re = re.compile(r'<name_array ', re.IGNORECASE)
    if tag_re.match(tag_str):
        elements = contents.split()
        elements = [lut[e] for e in elements]
        return True, ' '.join(elements)
    return False, None


def recurse_nodes(node):
    yield node
    if hasattr(node, 'children'):
        for n in node.children:
            yield from recurse_nodes(n)


def apply_inplace_rotation_r(node, rotation_mtx):
    inverse_rotation_mtx = np.linalg.inv(rotation_mtx)

    # Create axis-angle from rotation matrix
    axis, angle = quat2axangle(mat2quat(rotation_mtx))
    aax, aay, aaz = axis
    angle *= 180 / pi  # Yeah we out here

    # Create transform from axis-angle
    rot = RotateTransform(aax, aay, aaz, angle)
    node.transforms.insert(1, rot)

    for n in recurse_nodes(node):
        if not hasattr(n, 'matrix'):
            return
        # Decompose node matrix
        t, r, _, _ = decompose(n.matrix)

        # Apply inverse rotation to current translation
        t = inverse_rotation_mtx.dot(t)
        tx, ty, tz = t
        translate = TranslateTransform(tx, ty, tz)

        # HACK: translate is generally the first transform applied
        # Remove translate
        del n.transforms[0]
        # Add transforms to node to front of list (reverse order)
        n.transforms.insert(0, translate)


def get_all_primitives(node):
    primitives = set()
    for n in recurse_nodes(node):
        if isinstance(n, ControllerNode):
            controller = n.controller
            assert(isinstance(controller, collada.controller.Skin))
            geom = controller.geometry
            assert(isinstance(geom, collada.geometry.Geometry))
            prims = geom.primitives
            for prim in prims:
                primitives.add((geom, prim))
    return primitives


def rotate_prim(geom, prim, rotation_mtx):
    if isinstance(prim, collada.geometry.polylist.Polylist):
        verts = np.apply_along_axis(rotation_mtx.dot, 1, prim.vertex)
        norms = np.apply_along_axis(rotation_mtx.dot, 1, prim.normal)
        input_list = prim.getInputList()
        vert_list = input_list.inputs['VERTEX'][0]
        norm_list = input_list.inputs['NORMAL'][0]
        vert_id = vert_list.source[1:] # Remove # mark
        norm_id = norm_list.source[1:] # Remove # mark
        vert_source = geom.sourceById[vert_id]
        norm_source = geom.sourceById[norm_id]
        vert_source.data = verts
        norm_source.data = norms
    return prim


def repair_transforms(dae):
    assert(isinstance(dae, Collada))
    scene = dae.scene
    assert(isinstance(scene, collada.scene.Scene))
    root_nodes = scene.nodes
    for node in root_nodes:
        assert(isinstance(node, collada.scene.Node))
        root_mtx = node.matrix
        _, root_rot_mtx, _, _ = decompose(root_mtx)
        root_rot_inverse = np.linalg.inv(root_rot_mtx)
        apply_inplace_rotation_r(node, root_rot_inverse)
        primdata = get_all_primitives(node)
        for geom, prim in primdata:
            rotate_prim(geom, prim, root_rot_mtx)


def run(infile_path, outfile_path=None):
    base, ext = os.path.splitext(infile_path)
    outfile_path = outfile_path or f'{base}-fixed{ext}'
    pieces_re = re.compile(r'(\<[^>]*>)')
    with open(infile_path, 'r', encoding='utf-8') as infile:
        working_copy = []
        # For some strange reason, pycollada expects BytesIO despite its
        # documentation mentioning StringIO...???
        with io.BytesIO() as tempfile:
            sid_to_name = {}
            for line in infile:
                pieces = pieces_re.split(line)
                repaired_pieces = []
                for piece in pieces:
                    valid, parsed, repaired = parse_joint_tag(piece)
                    if valid:
                        _type, _id, name, sid = parsed
                        sid_to_name[sid] = name
                        repaired_pieces.append(repaired)
                    else:
                        repaired_pieces.append(piece)
                working_copy.append(repaired_pieces)
            for pieces in working_copy:
                repaired_pieces = pieces[:1]
                for piece, next_piece in zip(pieces, pieces[1:]):
                    valid, repaired_next_piece = parse_name_array_tag(
                        piece, next_piece, sid_to_name)
                    if valid:
                        repaired_pieces.append(repaired_next_piece)
                    else:
                        repaired_pieces.append(next_piece)
                repaired_line = ''.join(repaired_pieces)
                tempfile.write(str.encode(repaired_line, 'utf-8'))

            tempfile.seek(0)
            dae = Collada(tempfile)
            repair_transforms(dae)
            dae.filename = outfile_path

            with open(outfile_path, 'wb') as outfile:
                dae.write(outfile)



def main():
    parser = ArgumentParser(
        description='Cinema 4D COLLADA file format fixer (FFF).',
        epilog='Unless specified, outfile will be <infile>-fixed.<ext>')
    parser.add_argument('infile',
                        help='the input file path')
    parser.add_argument('outfile', nargs='?', default=None,
                        help='the output file path (optional)')
    args = parser.parse_args()
    run(args.infile, args.outfile)


if __name__ == '__main__':
    main()
