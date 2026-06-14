from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from vesper.commands.utils import copy_sdk_to_frontend


SUPPORTED_TEMPLATES = {
    "vanilla",
}

SUPPORTED_STYLES = {
    "none",
    "bootstrap",
    "tailwind",
}


def normalize_app_directory_name(name: str) -> str:
    normalized = name.strip().lower().replace(" ", "-")

    if not normalized:
        raise ValueError("App name cannot be empty.")

    return normalized


def validate_template(template: str) -> str:
    """
    Validate and normalize a template name.
    """

    normalized = template.strip().lower()

    if normalized not in SUPPORTED_TEMPLATES:
        print(f"Unsupported template: {template}")
        print("")
        print("Available templates:")

        for supported_template in sorted(SUPPORTED_TEMPLATES):
            print(f"  - {supported_template}")

        raise SystemExit(1)

    return normalized


def validate_styles(styles: str) -> str:
    """
    Validate and normalize a frontend styles option.
    """

    normalized = styles.strip().lower()

    if normalized not in SUPPORTED_STYLES:
        print(f"Unsupported styles option: {styles}")
        print("")
        print("Available styles:")

        for supported_styles in sorted(SUPPORTED_STYLES):
            print(f"  - {supported_styles}")

        raise SystemExit(1)

    return normalized


def ensure_npm_available() -> str:
    """
    Ensure npm is available before installing frontend style dependencies.
    """

    npm_path = shutil.which("npm")

    if npm_path is None:
        print("npm is required to install frontend style dependencies.")
        print("")
        print("Install Node.js and npm, then run this command again.")

        raise SystemExit(1)

    return npm_path


def run_npm_command(app_dir: Path, *args: str) -> None:
    """
    Run an npm command inside the generated Vesper app directory.
    """

    npm_path = ensure_npm_available()
    command = (npm_path, *args)

    try:
        subprocess.run(
            command,
            cwd=app_dir,
            check=True,
        )
    except FileNotFoundError as error:
        print("Could not execute npm.")
        print("")
        print("Make sure Node.js and npm are installed and available in your PATH.")
        raise SystemExit(1) from error
    except subprocess.CalledProcessError as error:
        print(f"npm command failed: {' '.join(command)}")
        raise SystemExit(error.returncode) from error


def write_package_json(app_dir: Path, package_name: str, styles: str) -> None:
    """
    Create a minimal package.json for frontend tooling.
    """

    scripts = {}

    if styles == "tailwind":
        scripts = {
            "dev:css": "tailwindcss -i ./frontend/styles/input.css -o ./frontend/styles/styles.css --watch",
            "build:css": "tailwindcss -i ./frontend/styles/input.css -o ./frontend/styles/styles.css --minify",
        }

    package_json = {
        "name": package_name,
        "version": "0.1.0",
        "private": True,
        "scripts": scripts,
    }

    (app_dir / "package.json").write_text(
        json.dumps(package_json, indent=2) + "\n",
        encoding="utf-8",
    )


def install_bootstrap(app_dir: Path, frontend_dir: Path) -> None:
    """
    Install Bootstrap with npm and copy the required files into frontend/vendor.

    The generated Vesper app can then run offline using local assets.
    """

    write_package_json(app_dir, app_dir.name, "bootstrap")

    run_npm_command(app_dir, "install", "bootstrap")

    bootstrap_dist = app_dir / "node_modules" / "bootstrap" / "dist"
    bootstrap_vendor_dir = frontend_dir / "vendor" / "bootstrap"

    css_dir = bootstrap_vendor_dir / "css"
    js_dir = bootstrap_vendor_dir / "js"

    css_dir.mkdir(parents=True, exist_ok=True)
    js_dir.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(
        bootstrap_dist / "css" / "bootstrap.min.css",
        css_dir / "bootstrap.min.css",
    )

    shutil.copyfile(
        bootstrap_dist / "js" / "bootstrap.bundle.min.js",
        js_dir / "bootstrap.bundle.min.js",
    )


def install_tailwind(app_dir: Path, frontend_dir: Path) -> None:
    """
    Install Tailwind with npm and generate a local CSS output file.

    The generated Vesper app can then run offline using frontend/styles/styles.css.
    """

    write_package_json(app_dir, app_dir.name, "tailwind")

    styles_dir = frontend_dir / "styles"
    styles_dir.mkdir(parents=True, exist_ok=True)

    input_css = """@import "tailwindcss";
"""

    (styles_dir / "input.css").write_text(input_css, encoding="utf-8")

    run_npm_command(app_dir, "install", "-D", "tailwindcss", "@tailwindcss/cli")
    run_npm_command(app_dir, "run", "build:css")


def create_index_html(name: str, styles: str) -> str:
    """
    Create the frontend index.html based on the selected styles option.
    """

    styles_head = ""
    bootstrap_script = ""

    body_class = ""
    main_class = ""
    title_class = ""
    text_class = ""
    button_class = ""

    if styles == "bootstrap":
        styles_head = '  <link rel="stylesheet" href="./vendor/bootstrap/css/bootstrap.min.css" />'
        bootstrap_script = '  <script src="./vendor/bootstrap/js/bootstrap.bundle.min.js"></script>'
        body_class = ' class="bg-light"'
        main_class = ' class="container py-5"'
        title_class = ' class="mb-3"'
        text_class = ' class="lead text-muted"'
        button_class = ' class="btn btn-primary"'

    elif styles == "tailwind":
        styles_head = '  <link rel="stylesheet" href="./styles/styles.css" />'
        body_class = ' class="min-h-screen bg-slate-950 text-white"'
        main_class = ' class="mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-8 py-10"'
        title_class = ' class="mb-4 text-5xl font-bold tracking-tight"'
        text_class = ' class="mb-8 max-w-2xl text-lg text-slate-300"'
        button_class = ' class="w-fit rounded-lg bg-blue-600 px-5 py-3 font-medium text-white shadow-lg shadow-blue-600/20 transition hover:bg-blue-500"'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{name}</title>
{styles_head}
</head>
<body{body_class}>
  <main{main_class}>
    <h1{title_class}>{name}</h1>

    <p{text_class}>
      Welcome to your Vesper application.
    </p>

    <button id="hello-button"{button_class}>Call Python</button>
  </main>

  <!-- VESPER SDK: DO NOT REMOVE. Required for Python <-> JavaScript communication. -->
  <script src="./vesper.js"></script>
{bootstrap_script}

  <script>
    document.getElementById("hello-button").addEventListener("click", async () => {{
      try {{
        const result = await vesper.invoke("hello", {{
          name: "Vesper"
        }});

        console.log(result);
        alert(result);
      }} catch (error) {{
        console.error(error);
        alert(error.message);
      }}
    }});
  </script>
</body>
</html>
"""


def create_app_py(name: str) -> str:
    """
    Create the Python entrypoint for the generated Vesper app.
    """

    return f'''from vesper import App


app = App(
    title="{name}",
    width=900,
    height=600,
    resizable=True,
    debug=True,
)


@app.command("hello")
def hello(name: str = "World") -> str:
    return f"Hello, {{name}}!"


if __name__ == "__main__":
    app.run()
'''


def print_next_steps(app_dir_name: str, styles: str) -> None:
    """
    Print the recommended next steps after creating a Vesper app.
    """

    print("")
    print("Next steps:")
    print(f"  cd {app_dir_name}")

    if styles == "tailwind":
        print("  npm run dev:css")
        print("  vesper run")
    else:
        print("  vesper run")


def create_vanilla_app(name: str, *, styles: str = "none") -> None:
    """
    Create a new Vesper app using the vanilla HTML/CSS/JS template.
    """

    app_dir_name = normalize_app_directory_name(name)
    app_dir = Path.cwd() / app_dir_name
    frontend_dir = app_dir / "frontend"

    if app_dir.exists():
        raise FileExistsError(f"Directory already exists: {app_dir}")

    normalized_styles = validate_styles(styles)

    frontend_dir.mkdir(parents=True)

    copy_sdk_to_frontend(frontend_dir)

    index_html = create_index_html(name, normalized_styles)
    app_py = create_app_py(name)

    (frontend_dir / "index.html").write_text(index_html, encoding="utf-8")
    (app_dir / "app.py").write_text(app_py, encoding="utf-8")

    if normalized_styles == "bootstrap":
        install_bootstrap(app_dir, frontend_dir)

    elif normalized_styles == "tailwind":
        install_tailwind(app_dir, frontend_dir)

    print(f"Created Vesper app: {app_dir}")
    print("Template: vanilla")
    print(f"Styles: {normalized_styles}")

    print_next_steps(app_dir_name, normalized_styles)


def create_app(
    name: str,
    *,
    template: str = "vanilla",
    styles: str = "none",
) -> None:
    """
    Create a new Vesper app using the selected template and styles option.
    """

    normalized_template = validate_template(template)
    normalized_styles = validate_styles(styles)

    if normalized_template == "vanilla":
        create_vanilla_app(
            name,
            styles=normalized_styles,
        )
        return

    raise RuntimeError(f"Unhandled template: {normalized_template}")


def add_init_parser(subparsers: argparse._SubParsersAction) -> None:
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new Vesper project."
    )

    init_subparsers = init_parser.add_subparsers(dest="init_target")

    init_app_parser = init_subparsers.add_parser(
        "app",
        help="Create a new Vesper app."
    )

    init_app_parser.add_argument(
        "--name",
        required=True,
        help="Name of the app to create."
    )

    init_app_parser.add_argument(
        "--template",
        default="vanilla",
        help="Template to use when creating the app. Available: vanilla."
    )

    init_app_parser.add_argument(
        "--styles",
        default="none",
        help="Frontend styles to use. Available: none, bootstrap, tailwind."
    )


def handle_init(args: argparse.Namespace) -> bool:
    if args.command == "init" and args.init_target == "app":
        create_app(
            args.name,
            template=args.template,
            styles=args.styles,
        )
        return True

    return False
