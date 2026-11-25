"""Bundle the same demo, model and licensed fonts into one offline HTML file."""
import base64
import mimetypes
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"


def export_demo():
    def embed(path):
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")

    html = (WEB / "index.html").read_text(encoding="utf-8")
    css = (WEB / "style.css").read_text(encoding="utf-8")
    css = re.sub(r"url\('([^']+)'\)", lambda m: "url('" + embed(WEB / m[1]) + "')", css)
    html = html.replace('<link rel="stylesheet" href="style.css">', "<style>" + css + "</style>")
    html = re.sub(r'((?:src|href)=")(assets/[^"]+)(")', lambda m: m[1]+embed(WEB / m[2])+m[3], html)
    scripts = re.findall(r'<script defer src="([^"]+)"></script>', html)
    html = re.sub(r'<script defer src="[^"]+"></script>', "", html)
    # Inline scripts execute immediately. Append after the form has been parsed.
    inline = []
    for filename in scripts:
        code = (WEB / filename).read_text(encoding="utf-8").replace("</script", "<\\/script")
        inline.append("<script>" + code + "</script>")
    notice = (WEB / "assets" / "FONT-LICENSE.txt").read_text(encoding="utf-8").replace("--","—")
    html = html.replace("</body>", "\n".join(inline) + "\n<!-- Bundled font notices\n" + notice + "\n-->\n</body>")
    output = ROOT / "LensCent_Demo.html"
    output.write_text(html, encoding="utf-8")
    return output


if __name__ == "__main__":
    print(export_demo())
