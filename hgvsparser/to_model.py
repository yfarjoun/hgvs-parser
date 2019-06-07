"""
Convert from the lark based parse tree to the dictionary variant model.
"""

from lark import Tree
from lark.lexer import Token


def convert(parse_tree):
    """
    Parse tree to nested dictionary model converter.

    :param parse_tree: Lark based parse tree.
    :return: Nested dictionary equivalent for the parse tree.
    """
    model = {}
    if isinstance(parse_tree, Tree):
        for child in parse_tree.children:
            if isinstance(child, Token):
                if child.type == 'COORDINATE_SYSTEM':
                    model['coordinate_system'] = child.value
            elif isinstance(parse_tree, Tree):
                if child.data == 'reference':
                    model['reference'] = reference_to_model(child)
                elif child.data == 'variants':
                    model['variants'] = variants_to_model(child)
    return model


def reference_to_model(reference_tree):
    if len(reference_tree.children) == 1:
        return {'id': reference_tree.children[0].value}
    elif len(reference_tree.children) == 2:
        return {'id': reference_tree.children[0].value,
                'selector': reference_to_model(reference_tree.children[1])}


def variants_to_model(variants_tree):
    variants = []
    for variant in variants_tree.children:
        variants.append(variant_to_model(variant))
    return variants


def inserted_to_model(inserted_tree):
    inserted = []
    for inserted_subtree in inserted_tree.children:
        insert = {}
        for insert_part in inserted_subtree.children:
            if isinstance(insert_part, Token):
                if insert_part.type == 'SEQUENCE':
                    insert.update({'sequence': insert_part.value,
                                   'source': 'description'})
                elif insert_part.type == 'INVERTED':
                    insert['inverted'] = True
            elif isinstance(insert_part, Tree):
                if insert_part.data == 'location':
                    location = location_to_model(insert_part)
                    if convert_location_to_length(location):
                        insert['length'] = length_to_model(insert_part)
                    else:
                        insert['location'] = location_to_model(insert_part)
                        insert['source'] = 'reference'
                elif insert_part.data == 'length':
                    insert['length'] = length_to_model(insert_part)
                elif insert_part.data == 'description':
                    for description_part in insert_part.children:
                        if isinstance(description_part, Token) and \
                                description_part.type == 'COORDINATE_SYSTEM':
                            insert['coordinate_system'] = description_part.value
                        elif description_part.data == 'variants':
                            if len(description_part.children) != 1:
                                raise Exception('Nested descriptions?')
                            variant = description_part.children[0]
                            if len(variant.children) != 1:
                                raise Exception('Nested descriptions?')
                            else:
                                insert['location'] = \
                                    location_to_model(
                                        variant.children[0])
                        elif description_part.data == 'reference':
                            insert['source'] = reference_to_model(
                                description_part)
        inserted.append(insert)
    return inserted


def deleted_to_model(deleted):
    deleted = deleted.children[0]
    if isinstance(deleted, Token):
        return [{'sequence': deleted.value,
                'source': 'description'}]
    else:
        if len(deleted.children) == 1 and \
                isinstance(deleted.children[0], Token):
            return [{'source': 'description',
                    'length': int(deleted.children[0].value)}]


def variant_to_model(variant_tree):
    variant = {'location': location_to_model(
        variant_tree.children[0])}
    if len(variant_tree.children) == 2:
        variant_tree = variant_tree.children[1]
        variant['type'] = variant_tree.data
        variant['source'] = 'reference'
        if variant_tree.data == 'deletion':
            variant['deleted'] = inserted_to_model(variant_tree.children[0])
        else:
            variant['inserted'] = inserted_to_model(variant_tree.children[0])
    return variant


def point_to_model(point_tree):
    if point_tree.data == 'uncertain_point':
        return {**range_to_model(point_tree),
                **{'uncertain': True}}
    point = {'type': 'point'}
    for token in point_tree.children:
        if token.type == 'OUTSIDE_CDS':
            if token.value == '*':
                point['outside_cds'] = 'downstream'
            elif token.value == '-':
                point['outside_cds'] = 'upstream'
        elif token.type == 'NUMBER':
            point['position'] = int(token.value)
        elif token.type == 'UNKNOWN':
            point['uncertain'] = True
        elif token.type == 'OFFSET':
            if '?' in token.value:
                point['offset'] = {'uncertain': True}
                if '+' in token.value:
                    point['offset']['downstream'] = True
                elif '-' in token.value:
                    point['offset']['upstream'] = True
            else:
                point['offset'] = {'value': int(token.value)}
    return point


def range_to_model(range_tree):
    range_location = {'type': 'range',
                      'start': point_to_model(
                          range_tree.children[0]),
                      'end': point_to_model(
                          range_tree.children[1])}
    return range_location


def location_to_model(location_tree):
    location_tree = location_tree.children[0]
    if location_tree.data in ['point', 'uncertain_point']:
        return point_to_model(location_tree)
    elif location_tree.data == 'range':
        return range_to_model(location_tree)


def length_point_to_model(length_point_token):
    if length_point_token.type == 'UNKNOWN':
        return {'type': 'point',
                'uncertain': True}
    if length_point_token.type == 'NUMBER':
        return {'type': 'point',
                'value': length_point_token.value}


def length_to_model(length_tree):
    print(length_tree)
    if length_tree.data == 'length':
        length_tree = length_tree.children[0]
        if isinstance(length_tree, Token):
            return length_point_to_model(length_tree)
        elif length_tree.data == 'exact_range':
            return {'type': 'range',
                    'start': length_point_to_model(length_tree.children[0]),
                    'end': length_point_to_model(length_tree.children[1]),
                    'uncertain': True}

    if length_tree.data == 'location':
        length_tree = length_tree.children[0]
        if length_tree.data == 'point':
            return length_point_to_model(length_tree.children[0])


def is_regular_point(point):
    """
    i.e., 100 and not -100, *100, -1+100, etc.
    """
    if (point.get('outside_cds') is not None) or \
            (point.get('outside_cds') is not None):
        return False
    else:
        return True


def convert_location_to_length(location):
    """
    Check if a location is `N` or `(N_N)`, with `N` being a number or `?`.
    """
    if location.get('type') == 'point':
        return is_regular_point(location)
    elif location.get('type') == 'range':
        if is_regular_point(location['start']) and \
                is_regular_point(location['end']) and \
                location.get('uncertain') is True:
            return True
    return False
