"""
DAEFix

Repairs COLLADA .dae files exported from Cinema 4D so that they are
compatible with Second Life mesh upload.
"""

import re
import os, sys
from argparse import ArgumentParser


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
    :return:
    """
    tag_re = re.compile(r'<name_array ', re.IGNORECASE)
    if tag_re.match(tag_str):
        elements = contents.split()
        elements = [lut[e] for e in elements]
        return True, ' '.join(elements)
    return False, None


def run(infile_path, outfile_path=None):
    base, ext = os.path.splitext(infile_path)
    outfile_path = outfile_path or f'{base}-fixed{ext}'
    pieces_re = re.compile(r'(\<[^>]*>)')
    with open(infile_path, 'r', encoding='utf-8') as infile:
        working_copy = []
        with open(outfile_path, 'w', encoding='utf-8') as outfile:
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

            outfile.seek(0)
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
                outfile.write(repaired_line)


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
