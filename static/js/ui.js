// Sof UI interaktivligi: menyu ochish/yopish va register formasidagi maydonlarni almashtirish.
// Bu fayl hech qachon serverdan ma'lumot olmaydi — barcha ma'lumot sahifa bilan birga keladi.

document.addEventListener("DOMContentLoaded", function () {
  setupNavbarToggle();
  setupRegisterRoleSwitch();
});

function setupNavbarToggle() {
  const toggleButton = document.querySelector("[data-toggle='navbar-menu']");
  const menu = document.getElementById("navbar-menu");
  if (!toggleButton || !menu) return;

  toggleButton.addEventListener("click", function () {
    menu.classList.toggle("is-open");
  });
}

function setupRegisterRoleSwitch() {
  const roleSelect = document.getElementById("register-role");
  const studentFields = document.getElementById("student-fields");
  const teacherFields = document.getElementById("teacher-fields");
  if (!roleSelect || !studentFields || !teacherFields) return;

  roleSelect.addEventListener("change", function () {
    const isTeacher = roleSelect.value === "teacher";
    teacherFields.hidden = !isTeacher;
    studentFields.hidden = isTeacher;
  });
}
