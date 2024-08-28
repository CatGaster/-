document.addEventListener('DOMContentLoaded', function() {
    const button = document.querySelector('#myButton');

    if (button) {
        button.addEventListener('click', function() {
            alert('Button clicked!');
        });
    }
});