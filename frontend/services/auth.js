import {
  clearAccessToken,
  getAuthenticatedUser,
  hasAccessToken,
  login as loginRequest,
  logout as logoutRequest,
  setAccessToken,
} from "./api.js?v=session-persistence";

let currentUser = null;

export async function loginUser(expectedRole, formData) {
  const username = formData.get("username")?.trim();
  const password = formData.get("password");
  if (!username || typeof password !== "string" || !password) {
    return null;
  }

  const response = await loginRequest(username, password);
  setAccessToken(response.access_token);
  if (response.user.role !== expectedRole) {
    try {
      await logoutRequest();
    } finally {
      clearAccessToken();
    }
    throw new Error("This account is not assigned to the selected workspace.");
  }

  currentUser = {
    role: response.user.role,
    name: response.user.username,
    username: response.user.username,
    identifier: response.user.subject_identifier,
  };
  return currentUser;
}

export function getCurrentUser() {
  return currentUser;
}

export async function restoreSession() {
  if (currentUser) {
    return currentUser;
  }
  if (!hasAccessToken()) {
    return null;
  }

  try {
    const user = await getAuthenticatedUser();
    currentUser = {
      role: user.role,
      name: user.username,
      username: user.username,
      identifier: user.subject_identifier,
    };
    return currentUser;
  } catch (error) {
    if (error?.status === 401) {
      clearAccessToken();
      return null;
    }
    throw error;
  }
}

export function isAuthenticated() {
  return currentUser !== null;
}

export async function logoutUser() {
  try {
    await logoutRequest();
  } finally {
    clearAccessToken();
    currentUser = null;
  }
}

export function getUserRole() {
  return currentUser?.role || null;
}
