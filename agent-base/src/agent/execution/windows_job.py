import win32job


class WindowsJob:
    def __init__(self):
        handle = win32job.CreateJobObject(None, "")

        try:
            info = win32job.QueryInformationJobObject(
                handle,
                win32job.JobObjectExtendedLimitInformation,
            )

            info["BasicLimitInformation"]["LimitFlags"] |= (
                win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )

            win32job.SetInformationJobObject(
                handle,
                win32job.JobObjectExtendedLimitInformation,
                info,
            )
        except BaseException:
            handle.Close()
            raise

        self._handle = handle

    def add_process(self, process_handle) -> None:
        if self._handle is None:
            raise RuntimeError("Job 已关闭")

        win32job.AssignProcessToJobObject(
            self._handle,
            process_handle,
        )

    def terminate(self) -> None:
        if self._handle is None:
            raise RuntimeError("Job 已关闭")

        win32job.TerminateJobObject(self._handle, 1)

    def close(self) -> None:
        if self._handle is not None:
            self._handle.Close()
            self._handle = None
