from pathlib import Path
import win32com.client
import pythoncom


path = Path(r"C:\Users\ali\repos\porsche\UTM_data\PAG_UTM_Monthly Audit_26_with_traffic_light.pptx")

pythoncom.CoInitialize()
app = win32com.client.Dispatch("PowerPoint.Application")
app.Visible = 1
pres = app.Presentations.Open(str(path), WithWindow=False)
slide = pres.Slides.Item(2)

print("shapes", slide.Shapes.Count)
for i in range(1, slide.Shapes.Count + 1):
    shape = slide.Shapes.Item(i)
    try:
        auto = shape.AutoShapeType
    except Exception:
        auto = None
    try:
        fill = shape.Fill.ForeColor.RGB
    except Exception:
        fill = None
    try:
        line = shape.Line.ForeColor.RGB
    except Exception:
        line = None
    text = ""
    try:
        if shape.HasTextFrame == -1 and shape.TextFrame.HasText == -1:
            text = shape.TextFrame.TextRange.Text.replace("\r", " ").replace("\n", " / ")
    except Exception:
        pass
    print(i, "type", shape.Type, "auto", auto, "left", round(shape.Left,1), "top", round(shape.Top,1), "w", round(shape.Width,1), "h", round(shape.Height,1), "fill", fill, "line", line, "text", text)

pres.Close()
app.Quit()
pythoncom.CoUninitialize()
