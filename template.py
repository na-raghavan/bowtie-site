import os
import subprocess
import uuid
from flask import Flask, render_template, request, redirect, url_for, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['RESULTS_FOLDER'] = os.path.join(BASE_DIR, 'results')
app.config['ALLOWED_EXTENSIONS'] = {'fasta', 'fa', 'fastq', 'fq'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def run_bowtie2(reference_file, reads_file, index_name, mode, threads, options, output_file):
    try:
        build_cmd = [
            'bowtie2-build',
            os.path.join(app.config['UPLOAD_FOLDER'], reference_file),
            os.path.join(app.config['UPLOAD_FOLDER'], index_name)]
        subprocess.run(build_cmd, check=True)
        align_cmd = [
            'bowtie2',
            '-x', os.path.join(app.config['UPLOAD_FOLDER'], index_name),
            '-U', os.path.join(app.config['UPLOAD_FOLDER'], reads_file),
            '-S', os.path.join(app.config['RESULTS_FOLDER'], output_file),
            '--{}'.format(mode),
            '-p', str(threads)]
        align_cmd += options 
        subprocess.run(align_cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running bowtie2: {e}")
        return False

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        reference = request.files['reference']
        reads = request.files['reads']
        
        if reference and allowed_file(reference.filename) and reads and allowed_file(reads.filename):
            unique_id = str(uuid.uuid4())[:8]
            ref_filename = f"ref_{unique_id}.{reference.filename.rsplit('.', 1)[1].lower()}"
            reads_filename = f"reads_{unique_id}.{reads.filename.rsplit('.', 1)[1].lower()}"
            output_filename = f"output_{unique_id}.sam"
            reference.save(os.path.join(app.config['UPLOAD_FOLDER'], ref_filename))
            reads.save(os.path.join(app.config['UPLOAD_FOLDER'], reads_filename))
            
            options = []
            if preset := request.form.get('preset'): # Preset option
                options.append(f'--{preset}')
            mp_max = request.form.get('mp_max') # Mismatch penalties
            mp_min = request.form.get('mp_min')
            if mp_max or mp_min:
                mp_values = []
                if mp_max: mp_values.append(mp_max)
                if mp_min: mp_values.append(mp_min)
                options.extend(['--mp', ','.join(mp_values)])
            if ma := request.form.get('ma'): # Match bonus
                options.extend(['--ma', ma])
            if k := request.form.get('k'): # Reporting options
                options.extend(['-k', k])
            if request.form.get('all') == 'on':
                options.append('--all')
            if request.form.get('no_unal') == 'on': # Output options
                options.append('--no-unal')
            if request.form.get('dovetail') == 'on': # Paired-end options
                options.append('--dovetail')
            if seed := request.form.get('seed'): # Seed
                options.extend(['--seed', seed])
            
            success = run_bowtie2(
                ref_filename,
                reads_filename,
                request.form.get('index_name', 'index'),
                request.form.get('mode', 'end-to-end'),
                request.form.get('threads', 1),
                options,
                output_filename)
            
            if success:
                return redirect(url_for('download', filename=output_filename))
            else:
                return "Error processing files", 500
    return render_template('upload.html')

@app.route('/download/<filename>')
def download(filename):
    return render_template('download.html', filename=filename)

@app.route('/download_file/<filename>')
def download_file(filename):
    return send_from_directory(
        directory=os.path.abspath(app.config['RESULTS_FOLDER']),
        path=filename,
        as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)