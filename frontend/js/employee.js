const SUBMIT_LEAVE_API =
    "https://8s6b30rgtb.execute-api.ap-south-1.amazonaws.com/Prod/leave";

document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("form");

    if (!form) {
        console.error("Leave application form not found.");
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const employeeId = "EMP001";
        const employeeName = "Test Employee";

        const leaveType = document.querySelector("#leaveType")?.value;
        const startDate = document.querySelector("#startDate")?.value;
        const endDate = document.querySelector("#endDate")?.value;
        const reason = document.querySelector("#reason")?.value;

        if (!leaveType || !startDate || !endDate || !reason) {
            alert("Please fill in all leave details.");
            return;
        }

        if (new Date(endDate) < new Date(startDate)) {
            alert("End date cannot be before start date.");
            return;
        }

        const submitButton = form.querySelector("button[type='submit']");

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = "Submitting...";
        }

        try {
            const response = await fetch(SUBMIT_LEAVE_API, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    employee_id: employeeId,
                    employee_name: employeeName,
                    leave_type: leaveType,
                    start_date: startDate,
                    end_date: endDate,
                    reason: reason
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.message || data.error || "Unable to submit leave request."
                );
            }

            alert(
                "Leave request submitted successfully!\n\n" +
                "Request ID: " +
                (data.request_id || "Generated successfully")
            );

            form.reset();

        } catch (error) {
            console.error("Leave submission error:", error);
            alert("Unable to submit leave request.\n\n" + error.message);
        } finally {
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.textContent = "Submit Leave Request";
            }
        }
    });
});