The missing step: row grouping

You already noticed this in your debug output 👇

“To iterate over rows and columns, we need to group cells by row”

Exactly.

The correct way to use table.cells
Step 1: treat cells as geometry, not data

Each cell is just:

(x0, top, x1, bottom)

You must reconstruct rows yourself.

Step 2: group cells by top coordinate

PDF tables align rows horizontally, so cells in the same row have almost the same top.

def group_cells_by_row(cells, tolerance=3):
rows = []
for cell in sorted(cells, key=lambda c: c[1]): # sort by top
placed = False
for row in rows:
if abs(row[0][1] - cell[1]) <= tolerance:
row.append(cell)
placed = True
break
if not placed:
rows.append([cell])
return rows

Now you get:

[
[(cell11), (cell12), (cell13)],
[(cell21), (cell22), (cell23)]
]

🎉 Actual rows

Step 3: sort cells within each row by x0
for row in rows:
row.sort(key=lambda c: c[0]) # left → right

Now you have:

rows[row_index][col_index] → bbox

Now your original plan works 💥
for r, row in enumerate(rows):
for c, bbox in enumerate(row):
chars = page.within_bbox(bbox).chars
latex = build_latex_from_chars(chars)
table_data[r][c] = latex

No unpacking errors.
No regex hacks.
Full sub/superscript recovery.
