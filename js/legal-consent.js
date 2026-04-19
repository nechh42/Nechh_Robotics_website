document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector("form");
  if (!form) return;

  form.addEventListener("submit", function (e) {
    const checkboxes = document.querySelectorAll(".legal-consent input[type='checkbox']");
    let allChecked = true;

    checkboxes.forEach(cb => {
      if (!cb.checked) {
        allChecked = false;
      }
    });

    if (!allChecked) {
      e.preventDefault();
      alert("You must confirm age and accept all legal terms to continue.");
    }
  });
});
