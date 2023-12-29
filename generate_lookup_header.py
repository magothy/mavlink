import xml.etree.ElementTree as ET
from dataclasses import dataclass
from collections.abc import Iterator
import os
from argparse import ArgumentParser


@dataclass
class KeyValue:
    id: int
    name: str


@dataclass
class Enum:
    name: str
    entries: list[KeyValue]


@dataclass
class MessageDefinition:
    fname: str
    includes: list[str]
    messages: list[KeyValue]
    enums: list[Enum]


def parse_entries(enum: ET.Element) -> Iterator[KeyValue]:
    for idx, entry in enumerate(enum.findall("./entry")):
        name = entry.attrib["name"]
        try:
            value = int(entry.attrib["value"])
        except KeyError:
            value = idx

        yield KeyValue(value, name)


def parse_enums(root: ET.Element) -> Iterator[Enum]:
    for enum in root.findall("./enums/enum"):
        entries = list(parse_entries(enum))
        yield Enum(enum.attrib["name"], entries)


def parse_messages(root: ET.Element) -> Iterator[KeyValue]:
    for message in root.findall("./messages/message"):
        yield KeyValue(int(message.attrib["id"]), message.attrib["name"])


def parse_includes(root: ET.Element) -> Iterator[str]:
    for include in root.findall("./include"):
        yield include.text if include.text else ""


def parse_message_definition(fname: str) -> Iterator[MessageDefinition]:
    tree = ET.parse(fname)
    root = tree.getroot()

    messages = list(parse_messages(root))
    includes = list(parse_includes(root))
    enums = list(parse_enums(root))
    yield MessageDefinition(fname, includes, messages, enums)

    dirname = os.path.dirname(fname)
    for include in includes:
        yield from parse_message_definition(os.path.join(dirname, include))


def generate_header(input_fname, output_fname, messages: list[KeyValue], enums: dict[str, list[KeyValue]]) -> Iterator[str]:
    yield f'/*! \\file {os.path.basename(output_fname)}'
    yield f' *  This file was automatically generated from {os.path.basename(input_fname)}'
    yield ' *  Copyright 2023 Magothy River Technologies'
    yield ' */'
    yield ''
    yield '#pragma once'
    yield ''
    yield '#include <cstdint>'
    yield '#include <sstream>'
    yield '#include <string>'
    yield '#include <unordered_map>'
    yield ''
    yield 'inline const char* mavlink_lookup(uint32_t key, const std::unordered_map<uint32_t, const char*>& map) {'
    yield '    auto it = map.find(key);'
    yield '    if (it != map.end()) {'
    yield '        return it->second;'
    yield '    }'
    yield '    return "Unknown";'
    yield '}'
    yield ''
    yield ''
    yield 'inline std::string mavlink_pretty(uint32_t key, const std::unordered_map<uint32_t, const char*>& map) {'
    yield '    std::stringstream ss;'
    yield '    ss << mavlink_lookup(key, map) << "(" << key << ")";'
    yield '    return ss.str();'
    yield '}'
    yield ''

    yield 'static const std::unordered_map<uint32_t, const char*> MAVLINK_MSG_ID_LOOKUP = {'
    for message in sorted(messages, key=lambda x: x.id):
        yield f'    {{{message.id}, "{message.name}"}},'
    yield '};'
    yield ''
    yield 'inline const char* mavlink_msg_id_str(uint32_t msg_id) {'
    yield '    return mavlink_lookup(msg_id, MAVLINK_MSG_ID_LOOKUP);'
    yield '}'
    yield ''
    yield 'inline std::string mavlink_msg_id_pretty(uint32_t msg_id) {'
    yield '    return mavlink_pretty(msg_id, MAVLINK_MSG_ID_LOOKUP);'
    yield '}'
    yield ''

    for enum_name, enum_entries in sorted(enums.items(), key=lambda x: x[0]):
        yield f'static const std::unordered_map<uint32_t, const char*> MAVLINK_{enum_name}_LOOKUP = {{'
        for entry in sorted(enum_entries, key=lambda x: x.id):
            yield f'    {{{entry.id}, "{entry.name}"}},'
        yield '};'
        yield ''
        yield f'inline const char* mavlink_{enum_name.lower()}_str(uint32_t val) {{'
        yield f'    return mavlink_lookup(val, MAVLINK_{enum_name}_LOOKUP);'
        yield '}'
        yield ''
        yield f'inline std::string mavlink_{enum_name.lower()}_pretty(uint32_t val) {{'
        yield f'    return mavlink_pretty(val, MAVLINK_{enum_name}_LOOKUP);'
        yield '}'
        yield ''


def main(input_fname, output_fname):
    definitions = list(parse_message_definition(input_fname))

    all_enum_names = set()
    for definition in definitions:
        for enum in definition.enums:
            all_enum_names.add(enum.name)
    all_enum_names = sorted(all_enum_names)

    all_messages = []
    all_enums = {}
    for definition in definitions:
        all_messages.extend(definition.messages)

        for enum in definition.enums:
            if enum.name not in all_enums:
                all_enums[enum.name] = []
            all_enums[enum.name].extend(enum.entries)

    with open(output_fname, "w") as f:
        for line in generate_header(input_fname, output_fname, all_messages, all_enums):
            f.write(line + "\n")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("input_fname", help="Path to message definition XML file")
    parser.add_argument("output_fname", help="Path to output file")
    args = parser.parse_args()
    main(args.input_fname, args.output_fname)
