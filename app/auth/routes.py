# Authentication routes - MOVED TO MEMBERS BLUEPRINT
# This file is kept for reference but all routes have been moved to:
# app/members/routes.py with /auth/ prefix
#
# Old routes → New routes:
# /auth/login → /members/auth/login
# /auth/logout → /members/auth/logout  
# /auth/reset_password → /members/auth/reset_password
# /auth/reset_password/<token> → /members/auth/reset_password/<token>
# /auth/profile → /members/auth/profile
# /auth/change_password → /members/auth/change_password
#
# This blueprint can be removed once all references are updated to use the members blueprint.

from app.auth import bp

# No routes defined - all moved to members blueprint