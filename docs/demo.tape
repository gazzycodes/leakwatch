# Record the demo GIF with VHS:  vhs docs/demo.tape
# Produces docs/demo.gif. On Windows, run under WSL or the Windows VHS build.

Output docs/demo.gif

Set FontSize 16
Set Width 1280
Set Height 720
Set Padding 20
Set Theme "Catppuccin Mocha"

# Use `python -m leakwatch` so it works without the Scripts dir on PATH.
Type "python -m leakwatch theguardian.com"
Sleep 600ms
Enter

# Let the page load and the dashboard stream in.
Sleep 22s

# Quit the dashboard.
Type "q"
Sleep 1s
