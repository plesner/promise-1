import promise
import sys
import traceback
import abc


class CapturedStack(object):
    """Represents a captured stack trace."""

    def format(self):
        """Returns this stack formatted as a list of strings."""
        pass


class ExceptionTraceback(CapturedStack):
    """An exception traceback captured during active exception handling."""

    def __init__(self, exc_info):
        self._exc_info = exc_info

    @staticmethod
    def capture_for(reason):
        """
        Attempts to capture an exception traceback for the given exception. If
        we're not currently handing that exception None is returned.
        """
        (type, value, tb) = sys.exc_info()
        if value is reason:
            return ExceptionTraceback((type, value, tb.tb_next))
        else:
            return None

    def format(self, reason):
        return traceback.format_exception(*self._exc_info)


class ExtractedStack(CapturedStack):
    """
    A stack from outside exception handling captured using the traceback library.
    """

    def __init__(self, stack):
        self._stack = stack

    @staticmethod
    def capture(frame_skip_count):
        """
        Captures and returns the current stack.
        """
        skip_count = frame_skip_count + 1
        stack = traceback.extract_stack()
        if skip_count > 0:
            stack = stack[:-skip_count]
        return ExtractedStack(stack)

    def format(self, reason):
        stack_strings = traceback.format_list(self._stack)
        exception_strings = traceback.format_exception_only(type(reason), reason)
        return stack_strings + exception_strings


class Trace(object):

    def __init__(self, reason, origin, cause_trace):
        # The exception that caused this link in the trace to occur.
        self._reason = reason
        # The captured stack that shows where this link happened.
        self._origin = origin
        # The link that represents whatever caused this link to be rejected.
        self._cause_trace = cause_trace
        # Once this trace has been formatted this will hold the string lines
        # it represents.
        self._raw_lines = None

    def format(self):
        if not self._cause_trace:
            # If this is the top trace we don't have to worry about other traces
            # we just return the origin.
            return self.raw_lines
        prev_lines = self._cause_trace.raw_lines
        own_lines = self.raw_lines
        prev_trace = self._cause_trace.format()
        if len(own_lines) == 0:
            return prev_trace
        (has_trimmed, suffix) = self._trim_common_prefix(prev_lines, own_lines)
        if len(prev_trace) > 0:
            prev_trace = prev_trace + [
                "\n",
                "The above was the direct cause of rejecting the following promise:\n",
                "\n"]
            if has_trimmed:
                prev_trace = prev_trace + [
                    "  ... (the rest of the trace is the same as the above) ...\n"
                ]
        return prev_trace + suffix

    def print_trace(self, out=sys.stdout):
        out.write("".join(self.format()))

    @property
    def raw_lines(self):
        if self._raw_lines is None:
            if self._origin is None:
                self._raw_lines = []
            else:
                self._raw_lines = self._origin.format(self._reason)
        return self._raw_lines


    @staticmethod
    def _trim_common_prefix(prev, current):
        min_len = min(len(prev), len(current))
        if (min_len == 0) or (prev[0] != current[0]):
            return (False, current)
        for i in range(1, min_len):
            if prev[i] != current[i]:
                return (i > 1, current[i-1:])
        return (True, current[min_len-1:])


_DEFAULT_TRACING = promise.promise.TraceOptions(capture_trace=True, frame_skip_count=0)


class Promise(promise.Promise):

    def __init__(self, fn=None, trace_options=None):
        trace_options = trace_options or _DEFAULT_TRACING
        # Calling the super constructer may fail so we have to do this first.
        if trace_options.capture_trace:
            self._origin = ExtractedStack.capture(trace_options.frame_skip_count + 1)
        else:
            self._origin = None
        self._trace = None
        super(Promise, self).__init__(fn)

    def _mark_rejected(self, reason, cause, frame_skip_count):
        super(Promise, self)._mark_rejected(reason, cause, frame_skip_count)

        # First build the trace object using the promise's state.
        cause_trace = None
        if isinstance(cause, Promise):
            # If a cause is given we form the trace by capturing the place this
            # promise was created and pointing back to the cause.
            cause_trace = cause.rejection_trace
        else:
            # If no cause was given we have to assume this promise was the
            # ultimate cause, so we have to capture some extra info right here.
            synthetic_stack = ExceptionTraceback.capture_for(reason)
            if not synthetic_stack:
                # If we can get a traceback for the exception that caused this
                # rejection so we use this as the ultimate cause. If not we have
                # to fall back on capturing the stack right at this point.
                synthetic_stack = ExtractedStack.capture(frame_skip_count + 1)
            cause_trace = Trace(reason, synthetic_stack, None)

        self._trace = Trace(reason, self._origin, cause_trace)

        # Then clear the state, we don't need it anymore.
        self._origin = None

    def _mark_fulfilled(self, value):
        super(Promise, self)._mark_fulfilled(value)

        # Now that this promise has been fulfilled we can discard any tracing
        # related data.
        self._origin = None
        self._trace = None

    @property
    def rejection_trace(self):
        return self._trace
