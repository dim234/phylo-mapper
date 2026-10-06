# Third-party licenses

SeqGrove's own code is under the MIT license (see `LICENSE`). The Windows
download also includes the libraries below. Their full license texts are in
the `licenses` folder.

| Component | Version | License | Source |
|---|---|---|---|
| Qt for Python (PySide6, Shiboken6) and the Qt 6 libraries it includes | 6.11.2 | LGPL-3.0 | https://code.qt.io/cgit/pyside/pyside-setup.git (tag `v6.11.2`), Qt itself: https://download.qt.io/official_releases/qt/ |
| Python | 3.14 | PSF License | https://www.python.org/downloads/source/ |
| pandas | 3.0.6 | BSD-3-Clause | https://github.com/pandas-dev/pandas |
| NumPy (with the libraries it bundles) | 2.5.3 | BSD-3-Clause and others, see `licenses/numpy.txt` | https://github.com/numpy/numpy |
| python-dateutil | 2.9.0 | Apache-2.0 / BSD-3-Clause | https://github.com/dateutil/dateutil |
| six | 1.17.0 | MIT | https://github.com/benjaminp/six |
| tzdata | 2026.5 | Apache-2.0 | https://github.com/python/tzdata |

The exe launcher comes from PyInstaller, which is GPL-2.0 with an exception
that allows it to be used in programs under any license.

## About Qt (LGPLv3)

SeqGrove uses Qt for Python and Qt under the GNU Lesser General Public
License version 3. The texts are in `licenses/LGPL-3.0.txt` and
`licenses/GPL-3.0.txt` (the LGPL builds on the GPL).

- Qt and PySide6 are used unmodified, exactly as published on PyPI.
- The Qt and PySide6 libraries are separate files inside the app folder, under
  `_internal\PySide6` and `_internal\shiboken6`. You can replace them with your
  own build of the same version and the app will use yours.
- The source code for Qt and PySide6 is available at the links in the table above.
  If you have trouble getting it, open an issue on this project's GitHub page and
  I'll help you get a copy.
