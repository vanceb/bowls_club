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

## CSS and Styling Guidelines

**CRITICAL: Prioritize Bulma CSS classes over custom CSS**

### 1. Use Bulma CSS Wherever Possible
- **Always check Bulma documentation first** before writing custom CSS
- Bulma provides comprehensive styling for layouts, components, forms, and utilities
- Common Bulma patterns to use:
  - **Layout**: `.container`, `.columns`, `.column`, `.section`, `.box`
  - **Components**: `.button`, `.card`, `.table`, `.modal`, `.navbar`
  - **Forms**: `.field`, `.control`, `.input`, `.select`, `.textarea`
  - **Utilities**: `.is-primary`, `.is-success`, `.is-danger`, `.has-text-centered`
  - **Modifiers**: `.is-large`, `.is-fullwidth`, `.is-pulled-right`, `.is-hidden`

### 2. Ensure Application-Wide Consistency
- **Use consistent Bulma classes across all templates**
- Follow established patterns from existing templates
- Example consistent patterns:
  - Use `.button.is-primary` for main actions
  - Use `.button.is-light` for secondary actions  
  - Use `.table.is-striped.is-hoverable` for data tables
  - Use `.box` for content containers
  - Use `.field` and `.control` for all form elements

### 3. Custom CSS as Last Resort Only
- **Only create custom CSS when Bulma cannot achieve the requirement**
- Keep custom CSS to an absolute minimum
- **All custom CSS must go in `/app/static/css/custom.css`**
- Document the reason for custom CSS in comments
- Prefer CSS custom properties (variables) for reusable values

### Examples of Proper CSS Usage:

#### ✅ Good Practice - Use Bulma Classes:
```html
<!-- Use existing Bulma classes -->
<div class="box">
    <div class="buttons">
        <button class="button is-primary">Save</button>
        <button class="button is-light">Cancel</button>
    </div>
</div>
```

#### ❌ Bad Practice - Custom CSS for Bulma Features:
```html
<!-- DON'T create custom CSS for what Bulma already provides -->
<style>
.my-custom-button { 
    background: #00d1b2; 
    padding: 0.5rem 1rem; 
}
</style>
<button class="my-custom-button">Save</button>
```

#### ✅ Acceptable Custom CSS - When Bulma Insufficient:
```css
/* custom.css - Only when Bulma cannot achieve the specific requirement */
.workflow-stage-progress {
    /* Custom animation not available in Bulma */
    animation: pulse 2s infinite;
}
```

### CSS Development Process:
1. **Check existing templates** for similar styling patterns
2. **Review Bulma documentation** for available classes
3. **Try Bulma class combinations** before considering custom CSS
4. **Only add to custom.css** if Bulma truly cannot achieve the requirement
5. **Keep custom CSS minimal** and well-documented

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