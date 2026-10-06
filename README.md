# PhyloMapper

Desktop app that reads an aligned FASTA file, computes pairwise nucleotide
mismatch distances, and plots a phylogenetic tree (UPGMA or neighbor joining).

## Download

Grab `PhyloMapper.exe` from the [latest release](../../releases/latest) and run
it — no Python install needed (Windows 64-bit).

## Run from source

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

Command-line output (distance matrix plus optional Newick tree):

```powershell
.venv\Scripts\python main.py test-sequences.fasta --tree upgma
```

## Build the executable

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Installs dependencies into `.venv`, runs the tests, and writes
`dist\PhyloMapper.exe`.

## Notes

- Distances count differences at sites where both sequences have A/C/G/T;
  gaps and ambiguity codes are skipped. Sequences must be aligned (equal length).
- Leaf branches are drawn at least 5% of the tree depth so zero-length leaves
  don't sit on a split; branch-length labels and Newick export keep the true values.
