document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const files = document.getElementById('resumeInput').files;

    if (files.length > 10) {
        alert('Maximum 10 resumes allowed!');
        return;
    }

    if (files.length === 0) {
        alert('Please select at least one file!');
        return;
    }

    const uploadButton = e.target.querySelector('button');
    uploadButton.disabled = true;
    uploadButton.textContent = 'Uploading...';

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        // Store file_references globally for use during save
        window.fileReferences = data.file_references || {};
        displayPreview(data.resumes);
    } catch (error) {
        console.error('Error uploading files:', error);
        alert('An error occurred while uploading files.');
    } finally {
        uploadButton.disabled = false;
        uploadButton.textContent = 'Upload';
    }
});

// Display and sort selected file names
document.getElementById('resumeInput').addEventListener('change', (e) => {
    const files = e.target.files;
    const fileNamesSpan = document.getElementById('fileNames');
    
    if (files.length === 0) {
        fileNamesSpan.textContent = 'No file chosen';
        return;
    }

    const fileArray = Array.from(files);
    fileArray.sort((a, b) => {
        const nameA = a.name;
        const nameB = b.name;
        const numA = nameA.match(/\d+(\.\d+)?/);
        const numB = nameB.match(/\d+(\.\d+)?/);
        if (numA && numB) {
            return parseFloat(numA[0]) - parseFloat(numB[0]);
        } else if (numA || numB) {
            return numA ? -1 : 1;
        } else {
            return nameA.localeCompare(nameB);
        }
    });

    const ul = document.createElement('ul');
    fileArray.forEach(file => {
        const li = document.createElement('li');
        li.textContent = file.name;
        ul.appendChild(li);
    });

    fileNamesSpan.innerHTML = '';
    fileNamesSpan.appendChild(ul);
});

function displayPreview(resumes) {
    const tableBody = document.getElementById('resumeTableBody');
    tableBody.innerHTML = '';
    
    resumes.forEach(resume => {
        const row = document.createElement('tr');
        const fields = [
            'Date', 'Name', 'Email Id', 'Contact No', 'Current Location', 'Category',
            'Total Experience', 'Designation', 'Skills', 'CTC info',
            'No of companies worked with till today', 'Last company worked with', 'Loyalty %'
        ];

        if (resume.error) {
            const cell = document.createElement('td');
            cell.colSpan = fields.length;
            cell.textContent = `Error: ${resume.error} (${resume.original_filename})`;
            cell.style.color = 'red';
            row.appendChild(cell);
        } else {
            fields.forEach(field => {
                const cell = document.createElement('td');
                cell.textContent = resume[field] || '';
                row.appendChild(cell);
            });
        }

        tableBody.appendChild(row);
    });

    document.getElementById('previewSection').style.display = 'block';
    window.resumesToSave = resumes;
}

document.getElementById('saveButton').addEventListener('click', async () => {
    if (!window.resumesToSave || window.resumesToSave.length === 0) {
        alert('No resumes to save!');
        return;
    }

    const saveButton = document.getElementById('saveButton');
    saveButton.disabled = true;
    saveButton.textContent = 'Saving...';

    try {
        const response = await fetch('/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                resumes: window.resumesToSave,
                file_references: window.fileReferences // Send file references to the backend
            })
        });
        const result = await response.json();

        alert(result.message);
        document.getElementById('previewSection').style.display = 'none';
        window.resumesToSave = [];
        window.fileReferences = {}; // Clear file references after saving
        document.getElementById('resumeInput').value = '';
        document.getElementById('fileNames').textContent = 'No file chosen';
    } catch (error) {
        console.error('Error saving to sheet:', error);
        alert('An error occurred while saving to the sheet.');
    } finally {
        saveButton.disabled = false;
        saveButton.textContent = 'Save';
    }
});