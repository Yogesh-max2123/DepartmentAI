const AUTH_STORAGE_KEY = "departmentai_dev_session";


export function loginUser(role, formData) {

    let user = null;


    if (role === "STUDENT") {

        user = {
            role: "STUDENT",
            name: formData.get("studentName")?.trim(),
            identifier: formData.get("registrationNumber")?.trim()
        };

    }


    if (role === "OFFICIAL") {

        user = {
            role: "OFFICIAL",
            name: formData.get("officialName")?.trim(),
            identifier: formData.get("officialId")?.trim()
        };

    }


    if (role === "DUGC") {

        user = {
            role: "DUGC",
            name: "DUGC",
            identifier: formData.get("dugcId")?.trim()
        };

    }


    if (!user || !user.identifier) {
        return null;
    }


    /*
     * Development-only authentication.
     *
     * The session is intentionally kept in memory
     * only for the current page session.
     *
     * Real authentication will later be connected
     * to the DepartmentAI backend.
     *
     * Passwords are intentionally not stored.
     */

    return user;
}


export function getCurrentUser() {

    /*
     * Development mode:
     * Do not restore authentication after refresh.
     *
     * This ensures that the role-selection login
     * screen is shown whenever the page is refreshed.
     */

    return null;
}


export function isAuthenticated() {

    return getCurrentUser() !== null;

}


export function logoutUser() {

    localStorage.removeItem(AUTH_STORAGE_KEY);

}


export function getUserRole() {

    const user =
        getCurrentUser();

    return user?.role || null;

}