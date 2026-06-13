import requests

mermaid_code = """
flowchart TD
    subgraph mine["<b>mine</b>"]
        mine_vars[/"<b>mine</b> vars<br><i>var1</i><br><i>var2</i>"\]
        style mine_vars fill:transparent,stroke-dasharray: 5 5
        generator(["<b>generator</b><br><i>var3</i>"])
    end
"""

response = requests.post("https://kroki.io/mermaid/png", data=mermaid_code.encode("utf-8"))
with open("test_kroki.png", "wb") as f:
    f.write(response.content)

print("Status:", response.status_code)
