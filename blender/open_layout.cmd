@echo off
rem Opens the paradise layout file in Blender with the 낙원 배치 panel (sidebar N) and the live link to Claude.
rem Rebuild the .blend first if the scene code changed:
rem   blender -b --factory-startup -P pitch_frames.py -- --work %%TEMP%%\akb --cover ..\akmu-pitch\refs\official\cover_flowering.jpg --out %%TEMP%%\akb\out\layout_build --layout-blend %%TEMP%%\akb\layout\paradise_layout_v3.blend
set "BL=C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
start "" "%BL%" "%TEMP%\akb\layout\paradise_layout_v3.blend" --python "%~dp0layout_tools.py"
