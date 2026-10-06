import argparse
from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


VALID_BASES = frozenset("ACGTURYSWKMBDHVN-.")
COMPARABLE_BASES = frozenset("ACGT")
TREE_METHODS = ("nj", "upgma")


def parse_fasta(lines: Iterable[str]) -> Dict[str, str]:
    """Parse FASTA records, using the first word of each header as its name."""
    sequences: Dict[str, str] = {}
    current_name: Optional[str] = None
    current_sequence: List[str] = []
    header_line = 0

    def save_record() -> None:
        if current_name is None:
            return
        if not current_sequence:
            raise ValueError(
                "FASTA record {!r} (header on line {}) has no sequence".format(
                    current_name, header_line
                )
            )
        sequences[current_name] = "".join(current_sequence)

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue

        if line.startswith(">"):
            save_record()
            header = line[1:].strip()
            if not header:
                raise ValueError(
                    "FASTA header on line {} has no identifier".format(line_number)
                )
            name = header.split()[0]
            if name in sequences:
                raise ValueError(
                    "Duplicate FASTA identifier {!r} on line {}".format(
                        name, line_number
                    )
                )
            current_name = name
            current_sequence = []
            header_line = line_number
            continue

        if current_name is None:
            raise ValueError(
                "Sequence data found before the first FASTA header on line {}".format(
                    line_number
                )
            )

        sequence_line = "".join(line.split()).upper()
        for base in sequence_line:
            if base not in VALID_BASES:
                raise ValueError(
                    "Invalid nucleotide {!r} in FASTA record {!r} on line {}".format(
                        base, current_name, line_number
                    )
                )
        current_sequence.append(sequence_line)

    save_record()
    if not sequences:
        raise ValueError("No FASTA records found")
    return sequences


def read_fasta(path: Path) -> Dict[str, str]:
    """Read and parse a FASTA file encoded as UTF-8."""
    with path.open("r", encoding="utf-8") as fasta_file:
        return parse_fasta(fasta_file)


def calculate_distance(seq1: str, seq2: str) -> Optional[int]:
    """Count differences at unambiguous nucleotide sites. Returns None if there are none."""
    if len(seq1) != len(seq2):
        raise ValueError(
            "Sequences must have equal lengths to calculate distance "
            "(got {} and {})".format(len(seq1), len(seq2))
        )

    mismatches = 0
    comparable_sites = 0
    for position, (base1, base2) in enumerate(
        zip(seq1.upper(), seq2.upper()), start=1
    ):
        if base1 not in VALID_BASES:
            raise ValueError(
                "Invalid nucleotide {!r} at position {}".format(base1, position)
            )
        if base2 not in VALID_BASES:
            raise ValueError(
                "Invalid nucleotide {!r} at position {}".format(base2, position)
            )
        # RNA uracil and DNA thymine represent the same nucleotide here.
        if base1 == "U":
            base1 = "T"
        if base2 == "U":
            base2 = "T"
        if base1 in COMPARABLE_BASES and base2 in COMPARABLE_BASES:
            comparable_sites += 1
            if base1 != base2:
                mismatches += 1

    return mismatches if comparable_sites else None


def build_distance_matrix(
    sequences: Dict[str, str],
) -> pd.DataFrame:
    """Build a labeled, symmetric DataFrame of distances for aligned sequences."""
    if not sequences:
        raise ValueError("At least one sequence is required")

    names = list(sequences)
    expected_length = len(sequences[names[0]])
    for name, sequence in sequences.items():
        if len(sequence) != expected_length:
            raise ValueError(
                "Sequence {!r} has length {}; expected {}. "
                "Align all sequences before calculating distances.".format(
                    name, len(sequence), expected_length
                )
            )

    matrix: List[List[Optional[int]]] = [
        [0 if row == column else None for column in range(len(names))]
        for row in range(len(names))
    ]
    for i, name in enumerate(names):
        for j in range(i + 1, len(names)):
            other = names[j]
            distance = calculate_distance(sequences[name], sequences[other])
            matrix[i][j] = distance
            matrix[j][i] = distance
    return pd.DataFrame(matrix, index=names, columns=names, dtype="Int64")


@dataclass
class TreeNode:
    """A rooted tree node. ``branch_length`` is the distance to its parent."""

    name: Optional[str] = None
    children: List["TreeNode"] = field(default_factory=list)
    branch_length: float = 0.0

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def leaves(self) -> List["TreeNode"]:
        if self.is_leaf:
            return [self]
        return [leaf for child in self.children for leaf in child.leaves()]

    def to_newick(self) -> str:
        return self._newick_body() + ";"

    def _newick_body(self) -> str:
        label = self.name or ""
        if self.children:
            label = "({}){}".format(
                ",".join(
                    "{}:{:g}".format(child._newick_body(), child.branch_length)
                    for child in self.children
                ),
                label,
            )
        return label


def _distance_lookup(matrix: pd.DataFrame) -> Tuple[List[str], Dict[Tuple[int, int], float]]:
    if list(matrix.index) != list(matrix.columns):
        raise ValueError("Distance matrix must have matching row and column labels")
    if len(matrix.index) == 0:
        raise ValueError("At least one sequence is required")
    if matrix.isna().to_numpy().any():
        raise ValueError(
            "Cannot build a tree: some sequence pairs share no comparable sites"
        )
    names = [str(name) for name in matrix.index]
    values = matrix.to_numpy(dtype=float)
    distances = {
        (i, j): float(values[i][j])
        for i in range(len(names))
        for j in range(len(names))
        if i != j
    }
    return names, distances


def upgma(matrix: pd.DataFrame) -> TreeNode:
    """Build a rooted, ultrametric tree with UPGMA clustering."""
    names, pair_distances = _distance_lookup(matrix)
    # Each cluster: node, number of leaves, height of the node above the leaves.
    clusters: Dict[int, Tuple[TreeNode, int, float]] = {
        i: (TreeNode(name=name), 1, 0.0) for i, name in enumerate(names)
    }
    distances = dict(pair_distances)
    next_id = len(names)

    while len(clusters) > 1:
        ids = list(clusters)
        a, b = min(
            ((x, y) for index, x in enumerate(ids) for y in ids[index + 1 :]),
            key=lambda pair: distances[pair],
        )
        node_a, size_a, height_a = clusters.pop(a)
        node_b, size_b, height_b = clusters.pop(b)
        height = distances[(a, b)] / 2
        node_a.branch_length = max(height - height_a, 0.0)
        node_b.branch_length = max(height - height_b, 0.0)
        merged = TreeNode(children=[node_a, node_b])

        for other in clusters:
            distance = (
                distances[(a, other)] * size_a + distances[(b, other)] * size_b
            ) / (size_a + size_b)
            distances[(next_id, other)] = distance
            distances[(other, next_id)] = distance
        clusters[next_id] = (merged, size_a + size_b, height)
        next_id += 1

    return next(iter(clusters.values()))[0]


def neighbor_joining(matrix: pd.DataFrame) -> TreeNode:
    """Build a tree with neighbor joining, rooted on the midpoint of the final join."""
    names, pair_distances = _distance_lookup(matrix)
    nodes: Dict[int, TreeNode] = {i: TreeNode(name=name) for i, name in enumerate(names)}
    distances = dict(pair_distances)
    next_id = len(names)

    while len(nodes) > 2:
        ids = list(nodes)
        count = len(ids)
        totals = {i: sum(distances[(i, j)] for j in ids if j != i) for i in ids}
        a, b = min(
            ((x, y) for index, x in enumerate(ids) for y in ids[index + 1 :]),
            key=lambda pair: (count - 2) * distances[pair]
            - totals[pair[0]]
            - totals[pair[1]],
        )
        distance_ab = distances[(a, b)]
        length_a = distance_ab / 2 + (totals[a] - totals[b]) / (2 * (count - 2))
        length_a = min(max(length_a, 0.0), distance_ab)
        node_a, node_b = nodes.pop(a), nodes.pop(b)
        node_a.branch_length = length_a
        node_b.branch_length = distance_ab - length_a
        merged = TreeNode(children=[node_a, node_b])

        for other in nodes:
            distance = (
                distances[(a, other)] + distances[(b, other)] - distance_ab
            ) / 2
            distances[(next_id, other)] = distance
            distances[(other, next_id)] = distance
        nodes[next_id] = merged
        next_id += 1

    if len(nodes) == 1:
        return next(iter(nodes.values()))
    a, b = nodes
    half = distances[(a, b)] / 2
    nodes[a].branch_length = half
    nodes[b].branch_length = half
    return TreeNode(children=[nodes[a], nodes[b]])


def build_tree(matrix: pd.DataFrame, method: str = "nj") -> TreeNode:
    if method == "nj":
        return neighbor_joining(matrix)
    if method == "upgma":
        return upgma(matrix)
    raise ValueError(
        "Unknown tree method {!r}, expected one of {}".format(
            method, ", ".join(TREE_METHODS)
        )
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Calculate pairwise nucleotide mismatch counts from an aligned FASTA file."
    )
    parser.add_argument("fasta", type=Path, help="path to an aligned FASTA file")
    parser.add_argument(
        "--tree",
        choices=TREE_METHODS,
        help="also print a Newick tree built with this method",
    )
    args = parser.parse_args(argv)

    try:
        sequences = read_fasta(args.fasta)
        matrix = build_distance_matrix(sequences)
        tree = build_tree(matrix, args.tree) if args.tree else None
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(matrix.to_string(na_rep="NA"))
    if tree is not None:
        print()
        print(tree.to_newick())
    return 0


if __name__ == "__main__":
    sys.exit(main())
