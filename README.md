# PhyloMapper

A small desktop app for looking at how related some DNA sequences are. You give
it an aligned FASTA file, it counts the differences between every pair of
sequences, and it draws a phylogenetic tree from those counts.

This is a personal project. I built it with help from AI coding tools. It's
free for anyone to use, change, or share (MIT license, see `LICENSE`).

## Getting it

The easiest way on Windows is the ready-made exe. Download `PhyloMapper.exe`
from the [releases page](../../releases/latest) and double-click it. You don't
need Python installed.

Windows will probably show a "Windows protected your PC" warning the first time,
because the exe isn't signed. Click "More info" and then "Run anyway".

## How to use it

1. Click **Open FASTA** and pick your file. The sequences have to be aligned,
   so they all need the same length.
2. Choose a tree method. UPGMA is the default and lines all the tips up on the
   right. Neighbor joining usually fits the data better when sequences have
   changed at different rates.
3. Click **Build tree**.
4. Use **Export** to save the distance matrix (CSV), the tree (Newick), or a
   picture of the tree (PNG).

There's a small example file, `test-sequences.fasta`, you can try it with.

## Running from source

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

There's also a command line version that prints the distance matrix and,
if you ask for it, the tree in Newick format:

```powershell
.venv\Scripts\python main.py test-sequences.fasta --tree upgma
```

Run the tests with `.venv\Scripts\python -m unittest`.

## Building the exe yourself

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

This sets up `.venv`, runs the tests, and puts the result in `dist\PhyloMapper.exe`.

## How the distances work

The distance between two sequences is the number of positions where they have
different bases. Only positions where both sequences have a plain A, C, G or T
are counted. Gaps and ambiguity codes like N or R are skipped, and U is treated
the same as T.

In the tree picture, very short tip branches are stretched a little so the
names don't end up sitting on a split line. The numbers shown on the branches
and the exported Newick file still use the real lengths.
