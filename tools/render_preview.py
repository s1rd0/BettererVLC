"""Offline layout preview of Skins2 XML assets; this is not a VLC screenshot.

Use idle playback, unmuted audio, zero seek position and 50% volume. The
Playtree remains empty, matching an empty real playlist. Assets are composited
in XML order using their native bitmap/font sizes and explicit XML geometry.
"""

from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT / "skin"
BUILD = ROOT / "build"


def integer(node, key, default=0):
    return int(float(node.get(key, default)))


def main():
    theme = ET.parse(SKIN / "theme.xml").getroot()
    bitmaps = {}
    fonts = {}
    errors = []
    for node in theme.findall("Bitmap"):
        image_path = SKIN / node.get("file")
        if not image_path.exists() or not image_path.stat().st_size:
            errors.append(f'Missing bitmap: {node.get("id")}: {image_path}')
            continue
        bitmap = Image.open(image_path).convert("RGBA")
        alpha_color = node.get("alphacolor")
        if alpha_color:
            rgb = tuple(int(alpha_color[offset:offset+2],16) for offset in (1,3,5))
            pixels = bitmap.load()
            for y in range(bitmap.height):
                for x in range(bitmap.width):
                    if pixels[x,y][:3] == rgb:
                        pixels[x,y] = (*rgb,0)
        bitmaps[node.get("id")] = bitmap
    for node in theme.findall("Font"):
        fonts[node.get("id")] = ImageFont.truetype(str(SKIN / node.get("file")),integer(node,"size"))

    report = {"kind":"offline-XML-asset-preview", "native_vlc_screenshot":False, "errors":errors,"layouts":{}}
    main_window = theme.find("Window[@id='main']")
    BUILD.mkdir(exist_ok=True)
    for layout in main_window.findall("Layout"):
        layout_id = layout.get("id")
        if layout_id not in {"player","library"}:
            continue
        width,height = integer(layout,"width"),integer(layout,"height")
        output = Image.new("RGBA",(width,height),(0,0,0,255))
        states = {"vlc.hasVout":False,"vlc.isStopped":True,"vlc.isPlaying":False,"vlc.isMute":False,"main.isMaximized":False,"library.isActive":layout_id=="library"}
        bounds = []

        def visible(node):
            expression = node.get("visible","true").strip()
            if expression in {"true","false"}:
                return expression=="true"
            if expression.startswith("not "):
                return not states.get(expression[4:],False)
            return states.get(expression,True)

        def paste(bitmap,x,y,w=None,h=None):
            if w is not None and h is not None and bitmap.size!=(w,h):
                bitmap=bitmap.resize((w,h),Image.Resampling.LANCZOS)
            output.alpha_composite(bitmap,(x,y))
            return bitmap.size

        for node in layout:
            if not visible(node) or node.tag=="Video":
                continue
            x,y = integer(node,"x"),integer(node,"y")
            ident = node.get("id")
            size = None
            if node.tag in {"Image","Button","Checkbox"}:
                bitmap_id = node.get("image") if node.tag=="Image" else node.get("up") if node.tag=="Button" else node.get("up2") if states.get(node.get("state"),False) else node.get("up1")
                if bitmap_id not in bitmaps:
                    errors.append(f"{ident}: unknown bitmap {bitmap_id}")
                    continue
                bitmap = bitmaps[bitmap_id]
                w,h = integer(node,"width",bitmap.width),integer(node,"height",bitmap.height)
                size = paste(bitmap,x,y,w,h) if node.tag=="Image" and node.get("resize") in {"scale","scale2"} else paste(bitmap,x,y)
            elif node.tag=="Text":
                text = node.get("text","").replace("$T","00:00:00").replace("$D","00:00:00").replace("$N","VLC Media Player")
                font = fonts[node.get("font")]
                region_width = integer(node,"width")
                ascender,descender = font.getmetrics()
                text_layer = Image.new("RGBA",(region_width,ascender+descender+3),(0,0,0,0))
                draw = ImageDraw.Draw(text_layer)
                alignment = node.get("alignment","left")
                text_width = draw.textlength(text,font=font)
                text_x = (region_width-text_width)/2 if alignment=="center" else region_width-text_width if alignment=="right" else 0
                draw.text((text_x,0),text,font=font,fill=node.get("color","#FFFFFF"),anchor="lt")
                paste(text_layer,x,y)
                size = text_layer.size
                if text_width>region_width:
                    errors.append(f"{ident}: text requires {text_width:.1f}px, region is {region_width}px")
            elif node.tag=="Playtree":
                w,h=integer(node,"width"),integer(node,"height")
                ImageDraw.Draw(output).rectangle((x,y,x+w-1,y+h-1),fill=node.get("bgcolor1","#000000"))
                size=(w,h)
            elif node.tag=="Slider":
                fraction = .5 if node.get("value")=="volume" else 0
                background = node.find("SliderBackground")
                size=(0,0)
                if background is not None:
                    bitmap = bitmaps[background.get("image")]
                    frame_count = integer(background,"nbvert",1)
                    frame_height=bitmap.height//frame_count
                    frame=min(round(fraction*(frame_count-1)),frame_count-1)
                    bitmap=bitmap.crop((0,frame*frame_height,bitmap.width,(frame+1)*frame_height))
                    size=paste(bitmap,x,y,integer(node,"width",bitmap.width),frame_height)
                points=[tuple(map(float,p)) for p in re.findall(r'\((-?[\d.]+),\s*(-?[\d.]+)\)',node.get("points",""))]
                if len(points)>=2:
                    knob=bitmaps[node.get("up")]
                    point_x=points[0][0]+fraction*(points[-1][0]-points[0][0])
                    point_y=points[0][1]+fraction*(points[-1][1]-points[0][1])
                    paste(knob,round(x+point_x-knob.width/2),round(y+point_y-knob.height/2))
            if size:
                bounds.append({"id":ident,"tag":node.tag,"x":x,"y":y,"width":size[0],"height":size[1]})
                if x<0 or y<0 or x+size[0]>width or y+size[1]>height:
                    errors.append(f"{ident}: element outside {width}x{height} layout")
        target=BUILD/f"preview-{layout_id}.png"
        output.convert("RGB").save(target)
        report["layouts"][layout_id]={"width":width,"height":height,"preview":str(target.relative_to(ROOT)).replace("\\","/"),"bounds":bounds}
        print(f"Saved {target}")
    (BUILD/"preview-report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(f"Offline preview warnings: {len(errors)}")
    for error in errors:
        print(error)


if __name__=="__main__":
    main()
