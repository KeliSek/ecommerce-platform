# dashboard/decorators.py
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def vendor_required(view_func):
    """
    Restricts a view to authenticated users with is_vendor_admin=True.
    Anonymous users get redirected to login as usual. A logged-in customer
    who lands on /dashboard/ by guessing the URL gets a hard 403 instead of
    a silent redirect loop, so they know it's a permissions issue and not a
    broken login.
    """

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_vendor_admin:
            raise PermissionDenied("You do not have vendor dashboard access.")
        return view_func(request, *args, **kwargs)

    return _wrapped
