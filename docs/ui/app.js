const modeButtons = document.querySelectorAll("[data-mode]");
const workspaces = document.querySelectorAll("[data-workspace]");

function activateMode(mode) {
  modeButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
  workspaces.forEach((workspace) => {
    workspace.classList.toggle("active", workspace.dataset.workspace === mode);
  });
}

modeButtons.forEach((button) => {
  button.addEventListener("click", () => activateMode(button.dataset.mode));
});

const userFlowButtons = document.querySelectorAll("[data-user-page]");
const userViews = document.querySelectorAll("[data-user-view]");

function activateUserPage(page) {
  userFlowButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.userPage === page);
  });
  userViews.forEach((view) => {
    view.classList.toggle("active", view.dataset.userView === page);
  });
}

document.querySelectorAll("[data-user-go]").forEach((button) => {
  button.addEventListener("click", () => activateUserPage(button.dataset.userGo));
});

userFlowButtons.forEach((button) => {
  button.addEventListener("click", () => activateUserPage(button.dataset.userPage));
});

const adminNavButtons = document.querySelectorAll("[data-admin-page]");
const adminViews = document.querySelectorAll("[data-admin-view]");

function activateAdminPage(page) {
  const activeNavPage = page === "detail" ? "list" : page;
  adminNavButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.adminPage === activeNavPage);
  });
  adminViews.forEach((view) => {
    view.classList.toggle("active", view.dataset.adminView === page);
  });
}

document.querySelectorAll("[data-admin-go]").forEach((button) => {
  button.addEventListener("click", () => activateAdminPage(button.dataset.adminGo));
});

adminNavButtons.forEach((button) => {
  button.addEventListener("click", () => activateAdminPage(button.dataset.adminPage));
});
