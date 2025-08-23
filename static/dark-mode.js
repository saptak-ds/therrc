// This function handles the logic for applying and saving the dark mode theme.

function setupDarkMode() {
    const themeToggleBtn = document.getElementById('theme-toggle');
    const sunIcon = document.getElementById('theme-toggle-sun');
    const moonIcon = document.getElementById('theme-toggle-moon');

    // Function to apply the correct theme and icon state
    const applyTheme = () => {
        if (localStorage.getItem('theme') === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            // If dark mode is saved in localStorage OR it's the system preference and not set yet
            document.documentElement.classList.add('dark');
            if (sunIcon && moonIcon) {
                sunIcon.classList.remove('hidden');
                moonIcon.classList.add('hidden');
            }
        } else {
            document.documentElement.classList.remove('dark');
            if (sunIcon && moonIcon) {
                sunIcon.classList.add('hidden');
                moonIcon.classList.remove('hidden');
            }
        }
    };

    // Run the function on initial page load
    applyTheme();

    // Add click listener to the button
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            // Toggle the theme in localStorage
            if (localStorage.getItem('theme') === 'dark') {
                localStorage.setItem('theme', 'light');
            } else {
                localStorage.setItem('theme', 'dark');
            }
            // Re-apply the theme to reflect the change
            applyTheme();
        });
    }
}

// Ensure the DOM is fully loaded before running the script
document.addEventListener('DOMContentLoaded', setupDarkMode);
