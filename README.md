# Market Watch 📊

A Django-based market monitoring application with comprehensive linting and formatting for all file types.

## 🚀 Quick Start

1. **Create and activate a virtual environment**:

   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Unix/MacOS
   source venv/bin/activate
   ```

2. **Install Python dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Install Node.js dependencies** (for linters):

   ```bash
   npm install
   ```

4. **Set up environment variables**:

   Create a `.env` file in the project root with:

   ```env
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   DB_NAME=market_watch
   DB_USER=postgres
   DB_PASSWORD=your-password
   DB_HOST=localhost
   DB_PORT=5432
   ```

5. **Run migrations**:

   ```bash
   python manage.py migrate
   ```

6. **Reload Cursor/VS Code**: `Ctrl+Shift+P` → "Reload Window"

7. **Install recommended extensions** when prompted

8. **Start the development server**:

   ```bash
   python manage.py runserver
   ```

   Visit `http://127.0.0.1:8000/` in your browser.

9. **Start coding** - all files auto-format and lint on save! ✨

---

## 📦 Python Dependencies

The `requirements.txt` file includes all necessary Python packages:

### Core Framework

- **Django 4.2.16** - Web framework
- **djangorestframework 3.15.2** - REST API framework

### Data Processing

- **pandas 2.2.3** - Data manipulation and analysis
- **numpy 2.1.2** - Numerical computing (pandas dependency)

### Financial Data

- **yfinance 0.2.48** - Yahoo Finance market data

### Web Scraping

- **beautifulsoup4 4.12.3** - HTML/XML parsing
- **requests 2.32.3** - HTTP library
- **lxml 5.3.0** - Fast XML/HTML parser

### Database

- **psycopg2-binary 2.9.9** - PostgreSQL adapter

### Utilities

- **python-dateutil 2.9.0** - Date/time utilities
- **django-environ 0.11.2** - Environment variable management
- **cachetools 5.5.0** - Caching decorators
- **django-cors-headers 4.5.0** - CORS header management

### Development Tools

- **black 24.10.0** - Python code formatter
- **flake8 7.1.1** - Python linter
- **isort 5.13.2** - Import organizer

---

## 📦 Required VS Code Extensions

The project is configured with 8 essential extensions (see `.vscode/extensions.json`):

| Extension           | Purpose                 | ID                           |
| ------------------- | ----------------------- | ---------------------------- |
| **Python**          | Python language support | `ms-python.python`           |
| **Black Formatter** | Python code formatter   | `ms-python.black-formatter`  |
| **isort**           | Python import organizer | `ms-python.isort`            |
| **ESLint**          | JavaScript linter       | `dbaeumer.vscode-eslint`     |
| **Stylelint**       | CSS linter              | `stylelint.vscode-stylelint` |
| **HTMLHint**        | HTML linter             | `htmlhint.vscode-htmlhint`   |
| **Prettier**        | JSON formatter          | `esbenp.prettier-vscode`     |
| **Django**          | Django template support | `batisteo.vscode-django`     |

### Installation:

1. Open Command Palette: `Ctrl+Shift+P`
2. Type: "Extensions: Show Recommended Extensions"
3. Install all recommended extensions

---

## 💾 What Happens When You Save Files

### Python Files (`.py`)

```
Save File (Ctrl+S)
    ↓
✅ Flake8 Linter Runs
   - Checks code style (PEP 8)
   - Finds unused imports/variables
   - Validates line length
    ↓
🔧 Black Formatter Runs
   - Reformats code style
   - Fixes indentation
    ↓
📦 isort Organizes Imports
   - Sorts alphabetically
   - Groups by type (stdlib, third-party, first-party)
    ↓
⚡ Results Appear
   - Errors/warnings in Problems panel (Ctrl+Shift+M)
   - Inline squiggles in editor
```

### JavaScript Files (`.js`)

```
Save File (Ctrl+S)
    ↓
✅ ESLint Runs & Auto-Fixes
   - Checks syntax errors
   - Validates code style
   - Fixes quote styles, semicolons, indentation
    ↓
⚡ Unfixable errors shown in Problems panel
```

### CSS Files (`.css`)

```
Save File (Ctrl+S)
    ↓
✅ Stylelint Validates & Auto-Fixes
   - Checks CSS syntax
   - Fixes indentation, property order
   - Corrects color notation
    ↓
⚡ Errors shown in Problems panel
```

### HTML Files (`.html`)

```
Save File (Ctrl+S)
    ↓
✅ HTMLHint Validates
   - Checks HTML5 structure
   - Validates tag pairing
   - Checks required attributes (alt, etc.)
    ↓
🔧 HTML Formatter Runs
   - Fixes indentation (2 spaces)
```

### JSON Files (`.json`)

```
Save File (Ctrl+S)
    ↓
✅ Prettier Validates & Formats
   - Checks valid JSON syntax
   - Formats indentation (2 spaces)
   - Fixes trailing commas
```

### General Actions (All Files)

Every save also:

- ✂️ Trims trailing whitespace
- 📄 Ensures final newline exists
- 🔄 Uses CRLF line endings (Windows)

---

## 🖥️ Terminal Commands

### Linting (Check for Issues)

```bash
# Python
python -m flake8 .
python -m black --check .
python -m isort --check-only .

# JavaScript
npm run lint:js

# CSS
npm run lint:css

# HTML
npm run lint:html

# JSON
npm run lint:json

# All at once
npm run lint:all
```

### Formatting (Auto-fix)

```bash
# Python
python -m black .
python -m isort .

# JavaScript
npm run format:js

# CSS
npm run format:css

# JSON
npm run format:json

# All at once
npm run format:all
```

---

## ⌨️ Keyboard Shortcuts

| Action               | Shortcut                         |
| -------------------- | -------------------------------- |
| Save File            | `Ctrl+S`                         |
| View Problems Panel  | `Ctrl+Shift+M`                   |
| Format Document      | `Shift+Alt+F`                    |
| Quick Fix            | `Ctrl+.`                         |
| Go to Next Error     | `F8`                             |
| Go to Previous Error | `Shift+F8`                       |
| Reload Window        | `Ctrl+Shift+P` → "Reload Window" |

---

## 👁️ Viewing Linter Errors

### Problems Panel

- **Open**: `Ctrl+Shift+M` (or View → Problems)
- **Shows**: All linting errors and warnings from all files
- **Status Bar**: Current file's error count shown at bottom
- **Click**: Any error to jump directly to the line

### In-Editor Indicators

- **Red squiggles** 🔴 : Errors that must be fixed
- **Yellow squiggles** 🟡 : Warnings (optional fixes)
- **Blue squiggles** 🔵 : Informational hints
- **Hover**: Over any squiggle to see the full error message

### Real-Time Updates

- **As you type**: Linters run continuously in background
- **On save**: Full lint check runs + auto-fix applied
- **Status bar**: Shows `✓` when no errors, `✗ N` when errors present

---

## 🔧 Configuration Files

### Python

- **`.flake8`** - Flake8 linter configuration (max line length: 9999)
- **`pyproject.toml`** - Black and isort configuration

### JavaScript

- **`.eslintrc.json`** - ESLint configuration
  - 2-space indentation
  - Double quotes for strings
  - Browser environment

### CSS

- **`.stylelintrc.json`** - Stylelint configuration
  - Based on standard config
  - Legacy color notation supported
  - Flexible selector patterns

### HTML

- **`.htmlhintrc`** - HTMLHint configuration
  - Basic HTML5 validation
  - Required alt attributes
  - 2-space indentation

### JSON

- **`.prettierrc.json`** - Prettier configuration
  - 100 character line width
  - 2-space indentation
  - Windows line endings (CRLF)

### IDE Settings

- **`.vscode/settings.json`** - Controls all linters and formatters
  ```json
  {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll": "explicit"
    },
    "python.linting.lintOnSave": true,
    "eslint.run": "onSave"
  }
  ```

---

## 📋 What Each Linter Checks

### Flake8 (Python)

- Code style (PEP 8)
- Unused imports
- Undefined variables
- Line length
- Complexity

### ESLint (JavaScript)

- Code style and formatting
- Unused variables
- Missing semicolons
- Quote consistency
- Best practices

### Stylelint (CSS)

- CSS syntax errors
- Property order
- Color format consistency
- Selector patterns
- Font family quotes

### HTMLHint (HTML)

- HTML5 validity
- Tag pairing
- Attribute requirements (alt, etc.)
- ID uniqueness
- Character escaping

### Prettier (JSON)

- Consistent formatting
- Proper indentation
- Trailing commas
- Quote style

---

## 🔍 Common Issues & Solutions

### Linter not working in IDE?

- ✅ Ensure the extension is installed
- ✅ Reload the window: `Ctrl+Shift+P` → "Reload Window"
- ✅ Check Output panel: View → Output → Select linter from dropdown
- ✅ Verify extension is enabled: Check bottom status bar for linter icons

### Format on save not working?

- ✅ Check that `"editor.formatOnSave": true` is in settings
- ✅ Verify the correct formatter is set for the file type
- ✅ Make sure the file extension is correct
- ✅ Look for conflicting extensions that might override settings

### Linter running but not showing errors?

- ✅ Check Problems panel: `Ctrl+Shift+M`
- ✅ Verify linter is enabled in settings (check `.vscode/settings.json`)
- ✅ Check extension output: View → Output → Select the linter
- ✅ Try restarting: `Ctrl+Shift+P` → "Reload Window"

### Terminal commands not found?

- ✅ For npm commands: Run `npm install` first
- ✅ For Python: Install packages with `pip install black isort flake8`

### Too many errors appearing?

- ✅ This is normal when first setting up linting!
- ✅ Run auto-fix: `npm run format:all`
- ✅ Fix remaining errors manually or adjust rules in config files

---

## 📝 Best Practices

1. **Before committing**: Run `npm run lint:all` and `python -m flake8 .` to catch all errors
2. **Let auto-format work**: Save files frequently to trigger auto-formatting
3. **Don't fight the formatter**: Consistent style is more important than personal preference
4. **Review linter warnings**: They often catch bugs before runtime
5. **Keep configs in sync**: Terminal and IDE use the same config files
6. **Check Problems panel**: Review all warnings before committing (`Ctrl+Shift+M`)

---

## 🛠️ Customization

To adjust linting rules, edit the configuration files:

- **Python**: `.flake8` and `pyproject.toml`
- **JavaScript**: `.eslintrc.json`
- **CSS**: `.stylelintrc.json`
- **HTML**: `.htmlhintrc`
- **JSON**: `.prettierrc.json`

After changing configs, reload the window: `Ctrl+Shift+P` → "Reload Window"

---

## 🚫 Disable On-Save Actions (if needed)

To temporarily disable auto-formatting:

1. Open Command Palette: `Ctrl+Shift+P`
2. Search: "Format On Save"
3. Toggle off for current session

Or edit `.vscode/settings.json` and set:

```json
"editor.formatOnSave": false
```

---

## 📂 Project Structure

```
market-watch/
├── core/                    # Django core settings
├── data_visualization/      # Data visualization app
├── economic_overview/       # Economic data app
├── market_overview/         # Market data app
├── shared/                  # Shared utilities
├── .vscode/                 # VS Code configuration
│   ├── settings.json       # Linter and formatter settings
│   └── extensions.json     # Recommended extensions
├── .eslintrc.json          # JavaScript linter config
├── .stylelintrc.json       # CSS linter config
├── .htmlhintrc             # HTML linter config
├── .prettierrc.json        # JSON formatter config
├── .flake8                 # Python linter config
├── pyproject.toml          # Black and isort config
├── package.json            # npm scripts for linting
└── README.md               # This file
```

---

## 🤝 Contributing

1. Ensure all linters pass: `npm run lint:all` and `python -m flake8 .`
2. Format your code: `npm run format:all` and `python -m black .`
3. Check Problems panel for any remaining issues: `Ctrl+Shift+M`
4. Submit your pull request

---

## 📄 License

[Add your license here]
