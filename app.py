import os
from flask import Flask, redirect, render_template, request, session
import uuid
from werkzeug.utils import secure_filename
import xml.etree.ElementTree as ET

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'twb'}
UPLOAD_FOLDER = '/Users/p-73/PycharmProjects/flask/myproject/upload/'

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_PATH'] = 50000

def allowed_file(filename):
  return '.' in filename and \
         filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/upload", methods=['GET', 'POST'])
def index():
    session['uid'] = uuid.uuid4()
    if request.method == 'POST':
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filename_h = str(session['uid'])
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_h))
            # message = filename + " uploaded"
            df = get_calc(UPLOAD_FOLDER+filename_h)
            return render_template('output.html', filename=df)
        else:
            error = "Not a valid twb file"
            return render_template('upload.html', error=error)
    return render_template('upload.html')

def get_calc(file):
    # parse the twb file
    tree = ET.parse(file)
    root = tree.getroot()

    # create a dictionary of name and tableau generated name

    calcDict = {}

    for item in root.findall('.//column[@caption]'):
        if item.find(".//calculation") is None:
            continue
        else:
            calcDict[item.attrib['name']] = '[' + item.attrib['caption'] + ']'

    # list of calc's name, tableau generated name, and calculation/formula
    calcList = []

    for item in root.findall('.//column[@caption]'):
        if item.find(".//calculation") is None:
            continue
        else:
            if item.find(".//calculation[@formula]") is None:
                continue
            else:
                calc_caption = '[' + item.attrib['caption'] + ']'
                calc_name = item.attrib['name']
                calc_raw_formula = item.find(".//calculation").attrib['formula']
                calc_comment = ''
                calc_formula = ''
                for line in calc_raw_formula.split('\r\n'):
                    if line.startswith('//'):
                        calc_comment = calc_comment + line + ' '
                    else:
                        calc_formula = calc_formula + line + ' '
                for name, caption in calcDict.items():
                    calc_formula = calc_formula.replace(name, caption)

                calc_row = (calc_caption, calc_name, calc_formula, calc_comment)
                calcList.append(list(calc_row))

    # convert the list of calcs into a data frame
    data = calcList
    data.sort()
    # list(data for data, _ in itertools.groupby(data))
    data_dedup = [data[i] for i in range(len(data)) if i == 0 or data[i] != data[i - 1]]
    # data = pd.DataFrame(data, columns=['Name', 'Remote Name', 'Formula', 'Comment'])

    # remove duplicate rows from data frame
    # data = data.drop_duplicates(subset=None, keep='first', inplace=False)

    # export to csv
    # get the name of the file

    #base = os.path.basename(file)
    #os.path.splitext(base)
    #filename = os.path.splitext(base)[0]

    #data.to_csv(filename + '.csv')
    return data_dedup

if __name__ == "__main__":
    app.secret_key = 'AoAv38dAf3A0ZTvE392jdjsvRBKN72v765f?RT'
    app.run()