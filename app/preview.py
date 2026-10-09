"""Render originals locally without relying on browser PDF plug-ins."""
import io
import threading
import pypdfium2 as pdfium

# PDFium is not thread-safe. All renderer entry points share this lock.
RENDER_LOCK=threading.Lock()

def render_page(path,page_number):
    with RENDER_LOCK:
        pdf=pdfium.PdfDocument(str(path))
        try:
            if not 1<=page_number<=len(pdf): raise ValueError('Source page is outside this PDF.')
            page=pdf[page_number-1]
            try:
                width,height=page.get_size()
                scale=min(1.8,1600/max(width,height))
                bitmap=page.render(scale=scale)
                try:
                    image=bitmap.to_pil()
                    try:
                        out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()
                    finally: image.close()
                finally: bitmap.close()
            finally: page.close()
        finally: pdf.close()
