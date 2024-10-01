function initNavigationSearch(navigation) {
  const searchButtons = navigation.querySelectorAll(".js-search-button");
  const searchContainer = navigation.querySelector(".p-search-box");
  const searchInput = navigation.querySelector(".p-search-box__input");

  searchButtons.forEach((searchButton) => {
    searchButton.addEventListener("click", toggleSearch);
  });

  const overlay = navigation.querySelector(".p-navigation__search-overlay");
  if (overlay) {
    overlay.addEventListener("click", closeSearch);
  }

  function toggleSearch(e) {
    e.preventDefault();

    if (navigation.classList.contains("has-search-open")) {
      closeSearch();
    } else {
      closeSearch();
      openSearch(e);
    }
  }

  function openSearch(e) {
    e.preventDefault();
    const buttons = document.querySelectorAll(".js-search-button");

    buttons.forEach((searchButton) => {
      searchButton.setAttribute("aria-pressed", true);
    });

    navigation.classList.add("has-search-open");
    searchContainer.classList.add("is-active");
    searchInput.focus();
    document.addEventListener("keyup", keyPressHandler);
  }

  function closeSearch() {
    const buttons = document.querySelectorAll(".js-search-button");

    buttons.forEach((searchButton) => {
      searchButton.removeAttribute("aria-pressed");
    });

    navigation.classList.remove("has-search-open");
    searchContainer.classList.remove("is-active");
    document.removeEventListener("keyup", keyPressHandler);
  }

  function keyPressHandler(e) {
    if (e.key === "Escape") {
      closeSearch();
    }
  }
}

const navigation = document.querySelector("#navigation");
initNavigationSearch(navigation);
