#!/usr/bin/env python3
"""Shared front-matter parsing utilities."""
import re


def parse_front_matter(text):
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    yaml_lines = []
    end_index = -1
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = i
            break
        yaml_lines.append(line)
    if end_index == -1:
        return {}, text
    meta = simple_yaml_parse(yaml_lines)
    return meta, "\n".join(lines[end_index + 1:])


def simple_yaml_parse(lines):
    data = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r'^([A-Za-z0-9_-]+)\s*:\s*(.*)$', stripped)
        if not match:
            continue
        value = match.group(2).strip()
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        data[match.group(1)] = value
    return data
