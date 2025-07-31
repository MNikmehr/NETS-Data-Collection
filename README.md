# NETS-Data-Collection

https://github.com/tesseract-ocr/tesseract/releases (that's for me)

Open a new folder named "VIDEO"

Create a new file named tube_angle_analysis.py

Copy and paste the code within the new file.

Open a new terminal and run the following

pip install opencv-contrib-python
pip install numpy
pip install pytesseract
pip install pandas

then go to [https://github.com/tesseract-ocr/tesseract/releases](https://github.com/UB-Mannheim/tesseract/wiki)
Install the latest version and make sure the default path is C:\Program Files\Tesseract-OCR\tesseract.exe

Run the file, choose whether you want a single video or a folder (multiple videos)

Right-click the folder or the video you wish to annotate (located on the left side)

Copy the file/folder path, and paste it where it asks for the video name or folder path

Then follow the steps.

When selecting points on the screen, the initial point has to be the protractor origin, then the tip of the tube, then the 0, and the 90 angle.

Then circle a little box around the tube's tip where you selected a point, a box around the location that will be annotated, basically from the left side of the tube, all the way to the right, and only around the protractor, and finally, a box around the pressure gauge number (for recording).

Remember, if it's a folder, the point and box selection has to be repeated for all videos, until the testing setup is fixed in place (which will be done in the future).

