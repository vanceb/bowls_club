# Template Guidelines

This file provides guidance specific to working with HTML templates in this Flask application.

## Template Structure

### Base Template
- `base.html` - Main layout template with navigation, header, and footer
- All other templates extend base.html using `{% extends "base.html" %}`

### Template Categories
- **Authentication**: `login.html`, `pw_reset.html`, `pw_reset_request.html`
- **Member Management**: `add_member.html`, `edit_member.html`, `edit_profile.html`, `members.html`
- **Event Management**: `manage_events.html`, `add_event_team.html`, `edit_event_team.html`
- **Booking Management**: `bookings_table.html`, `manage_booking_teams.html`, `my_games.html`
- **Content Management**: `write_post.html`, `manage_posts.html`, `view_post.html`
- **Error Pages**: `403.html`, `404.html`, `500.html`

### Partials Directory
Reusable template components in `partials/`:
- `navbar.html` - Main navigation bar
- `masthead.html` - Page header section
- `footer.html` - Site footer
- `sidebar.html` - Sidebar content
- `notify.html` - Flash message notifications
- `post_item.html` - Individual post display component

## CSS Framework

### Bulma CSS
- Uses Bulma CSS framework for styling
- Common classes: `.container`, `.box`, `.button`, `.table`, `.field`, `.control`
- Layout: `.columns`, `.column`, `.level`, `.level-left`, `.level-right`
- Colors: `.is-primary`, `.is-success`, `.is-warning`, `.is-danger`
- Sizing: `.is-small`, `.is-medium`, `.is-large`

### Custom Styles
- Additional custom CSS in `/static/css/custom.css`
- Use Bulma classes first, custom CSS only when necessary

## JavaScript Guidelines

### Form Protection
- Use client-side protection for critical form submissions
- Disable submit buttons after first click to prevent duplicates
- Show loading states with spinners and text changes
- Include timeout fallbacks to re-enable buttons

### AJAX and Dynamic Content
- Use fetch() for API calls to load dynamic content
- Handle errors gracefully with try/catch blocks
- Update DOM elements responsively
- Maintain accessibility during dynamic updates

### Example Client-Side Form Protection
```javascript
const submitBtn = document.getElementById('submit-btn');
const form = document.querySelector('form');

form.addEventListener('submit', function(e) {
    if (submitBtn.disabled) {
        e.preventDefault();
        return false;
    }
    
    submitBtn.disabled = true;
    submitBtn.classList.add('is-loading');
    submitBtn.textContent = 'Processing...';
    
    // Timeout fallback
    setTimeout(() => {
        submitBtn.disabled = false;
        submitBtn.classList.remove('is-loading');
        submitBtn.textContent = 'Submit';
    }, 10000);
});
```

## Template Variables

### Common Variables
- `menu_items` - Main navigation menu configuration
- `admin_menu_items` - Admin navigation menu configuration
- `current_user` - Authenticated user object
- `title` - Page title for browser tab

### Form Variables
- Forms passed from routes (e.g., `form`, `booking_form`, `event_form`)
- Always include `{{ form.hidden_tag() }}` for CSRF protection
- Use proper form validation display with error messages

## Accessibility Guidelines

- Use semantic HTML elements
- Include proper ARIA labels for interactive elements
- Ensure keyboard navigation works correctly
- Provide alt text for images
- Use proper heading hierarchy (h1, h2, h3, etc.)

## Security Considerations

### CSRF Protection
- Always use `{{ form.hidden_tag() }}` in forms
- Never disable CSRF validation in templates
- Include CSRF tokens in AJAX requests

### Content Safety
- Use `{{ variable|safe }}` only for trusted content
- Escape user input by default
- Sanitize HTML content before rendering

### Example Secure Form
```html
<form method="POST">
    {{ form.hidden_tag() }}
    
    <div class="field">
        <label class="label">{{ form.name.label }}</label>
        <div class="control">
            {{ form.name(class="input") }}
        </div>
        {% for error in form.name.errors %}
            <p class="help is-danger">{{ error }}</p>
        {% endfor %}
    </div>
    
    <div class="field">
        <div class="control">
            <button type="submit" class="button is-primary">Submit</button>
        </div>
    </div>
</form>
```