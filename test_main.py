import unittest

import pandas as pd

from main import build_distance_matrix, build_tree, calculate_distance, parse_fasta


class FastaParsingTests(unittest.TestCase):
    def test_parses_multiline_sequences_and_uses_header_identifier(self):
        sequences = parse_fasta(
            [
                "; example alignment\n",
                ">sample_a description\n",
                "atgc\n",
                " gt\n",
                ">sample_b\n",
                "ATGCGT\n",
            ]
        )

        self.assertEqual(
            sequences, {"sample_a": "ATGCGT", "sample_b": "ATGCGT"}
        )

    def test_rejects_malformed_records(self):
        invalid_inputs = [
            (["ACGT\n"], "before the first FASTA header"),
            ([">\n", "ACGT\n"], "has no identifier"),
            ([">sample\n"], "has no sequence"),
            ([">sample\n", "ACGX\n"], "Invalid nucleotide"),
            ([">sample\n", "ACGT\n", ">sample another\n", "ACGT\n"], "Duplicate"),
            (["; comment\n"], "No FASTA records found"),
        ]
        for lines, message in invalid_inputs:
            with self.subTest(lines=lines):
                with self.assertRaisesRegex(ValueError, message):
                    parse_fasta(lines)


class DistanceTests(unittest.TestCase):
    def test_ignores_ambiguous_and_gap_sites_and_normalizes_uracil(self):
        self.assertEqual(calculate_distance("AUCR-N", "ATGT-A"), 1)

    def test_returns_none_when_no_sites_can_be_compared(self):
        self.assertIsNone(calculate_distance("NN--", "RR.."))

    def test_rejects_sequences_with_different_lengths(self):
        with self.assertRaisesRegex(ValueError, "equal lengths"):
            calculate_distance("ACGT", "ACG")
        with self.assertRaisesRegex(ValueError, "Invalid nucleotide"):
            calculate_distance("ACGX", "ACGT")

    def test_matrix_is_symmetric_and_requires_aligned_sequences(self):
        matrix = build_distance_matrix({"a": "ACGT", "b": "ATGT"})
        self.assertIsInstance(matrix, pd.DataFrame)
        self.assertEqual(list(matrix.index), ["a", "b"])
        self.assertEqual(list(matrix.columns), ["a", "b"])
        self.assertEqual(matrix.loc["a", "a"], 0)
        self.assertEqual(matrix.loc["a", "b"], 1)
        self.assertEqual(matrix.loc["b", "a"], 1)
        self.assertEqual(str(matrix.dtypes.iloc[0]), "Int64")

        with self.assertRaisesRegex(ValueError, "Align all sequences"):
            build_distance_matrix({"a": "ACGT", "b": "ACG"})

    def test_matrix_uses_pandas_missing_value_for_uncomparable_sequences(self):
        matrix = build_distance_matrix({"a": "NN--", "b": "RR.."})
        self.assertIs(matrix.loc["a", "b"], pd.NA)


class TreeTests(unittest.TestCase):
    # Additive distances for the tree ((a:1,b:2):1,(c:3,d:1)).
    MATRIX = pd.DataFrame(
        [[0, 3, 5, 3], [3, 0, 6, 4], [5, 6, 0, 4], [3, 4, 4, 0]],
        index=list("abcd"),
        columns=list("abcd"),
        dtype="Int64",
    )

    @staticmethod
    def path_length(tree, first, second):
        def path(node, target):
            if node.name == target:
                return [node]
            for child in node.children:
                found = path(child, target)
                if found:
                    return [node] + found
            return []

        path_a, path_b = path(tree, first), path(tree, second)
        shared = 0
        while shared < min(len(path_a), len(path_b)) and path_a[shared] is path_b[shared]:
            shared += 1
        return sum(n.branch_length for n in path_a[shared:] + path_b[shared:])

    def test_neighbor_joining_recovers_additive_distances(self):
        tree = build_tree(self.MATRIX, "nj")
        self.assertEqual(sorted(leaf.name for leaf in tree.leaves()), list("abcd"))
        for first in "abcd":
            for second in "abcd":
                if first < second:
                    self.assertAlmostEqual(
                        self.path_length(tree, first, second),
                        self.MATRIX.loc[first, second],
                    )

    def test_upgma_groups_closest_pair_with_ultrametric_heights(self):
        matrix = pd.DataFrame(
            [[0, 2, 6], [2, 0, 6], [6, 6, 0]], index=list("abc"), columns=list("abc")
        )
        tree = build_tree(matrix, "upgma")
        pair = next(child for child in tree.children if not child.is_leaf)
        self.assertEqual(sorted(leaf.name for leaf in pair.leaves()), ["a", "b"])
        self.assertEqual(tree.to_newick(), "(c:3,(a:1,b:1):2);")

    def test_tree_rejects_missing_distances_and_unknown_methods(self):
        matrix = build_distance_matrix({"a": "NN--", "b": "RR.."})
        with self.assertRaisesRegex(ValueError, "no comparable sites"):
            build_tree(matrix, "nj")
        with self.assertRaisesRegex(ValueError, "Unknown tree method"):
            build_tree(self.MATRIX, "parsimony")

    def test_single_sequence_tree_is_a_leaf(self):
        tree = build_tree(build_distance_matrix({"only": "ACGT"}), "nj")
        self.assertEqual(tree.to_newick(), "only;")


if __name__ == "__main__":
    unittest.main()
