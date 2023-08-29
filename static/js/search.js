import debounce from "./utility/debounce";

/*
  Init navigation controls
*/
function initNavigationSearch(navigationElement) {
  const navigation = navigationElement;
  const searchButtons = navigation.querySelectorAll(".js-search-button");
  const searchContainer = navigation.querySelector(".p-search-and-filter");
  const clearButton = navigation.querySelector(".p-search-and-filter__clear");
  const searchInput = navigation.querySelector(".p-search-and-filter__input");
  const resutlsPanel = navigation.querySelector(".p-search-and-filter__panel");
  const searchQuery = navigation.querySelector(".p-search-and-filter__search-query");

  searchButtons.forEach((searchButton) => {
    searchButton.addEventListener("click", toggleSearch);
  });

  clearButton.addEventListener("click", handleClearButton);

  searchInput.addEventListener("keyup", function (event) {
    if (searchInput.value === "") {
      clearButton.style.display = "none";
      resutlsPanel.style.display = "none";
    } else {
      clearButton.style.display = "block";
      resutlsPanel.style.display = "block";
    }
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
    var buttons = document.querySelectorAll(".js-search-button");

    buttons.forEach((searchButton) => {
      searchButton.setAttribute("aria-pressed", true);
    });

    navigation.classList.add("has-search-open");
    searchContainer.classList.add("is-active");
    searchInput.focus();
    document.addEventListener("keyup", keyPressHandler);
  }

  function handleClearButton() {
    searchInput.value = "";
    clearButton.style.display = "none";
    resutlsPanel.style.display = "none";
  }

  function closeSearch() {
    var buttons = document.querySelectorAll(".js-search-button");

    buttons.forEach((searchButton) => {
      searchButton.removeAttribute("aria-pressed");
    });

    navigation.classList.remove("has-search-open");
    searchContainer.classList.remove("is-active");
    handleClearButton();
    document.removeEventListener("keyup", keyPressHandler);
  }

  function keyPressHandler(e) {
    if (e.key === "Escape") {
      closeSearch();
    }
  }
}

var navigation = document.querySelector("#navigation");
initNavigationSearch(navigation);

/*
  Handle search
*/
let referenceDict;
const searchInput = document.querySelector(".p-search-and-filter__input");
const searchResults = document.querySelector(".p-search-and-filter__search-results");
const debouncedFetchSearchResults = debounce(fetchSearchResults, 200);
let lastFetchTime = 0; // To track the time of the last AJAX request
const delayBetweenRequests = 100; 

function fetchSearchResults(query) {
  if (query.length >= 2) {
    const currentTime = Date.now();
    const timeSinceLastFetch = currentTime - lastFetchTime;

    if (timeSinceLastFetch >= delayBetweenRequests) {
      lastFetchTime = currentTime; 
      fetch(`/search?q=${query}`)
        .then(results => results.json())
        .then(results => {
          searchResults.innerHTML = "";
          console.log(results)
          results.forEach((result) => {            
            let resultLinkCont = document.createElement("a");
            let docTitle = document.createElement("strong");
            let doctAuthor = document.createElement("p");
            let targetDoc = referenceDict[result.id];
            console.log("----_", targetDoc)
            
            if (!targetDoc || !targetDoc.breadcrumbs) {
              return;
            } else if (targetDoc.name.toLowerCase() == "index") {
              let parentFolder = targetDoc.breadcrumbs.slice(-1)[0].name;
              resultLinkCont.textContent = parentFolder;
            } else {
              resultLinkCont.textContent = targetDoc.name;
            }
            
            resultLinkCont.href = referenceDict[result.id].full_path;
            resultLinkCont.classList.add("p-search-and-filter__search-result");
            searchResults.append(resultLinkCont);
          });
        })
        .catch(error => {
          console.error("An error occurred fetching search results", error);
        });
    }
  } else {
    searchResults.innerHTML = "";
  }
}

async function fetchReferenceDict() {
  try {
      const response = await fetch('/doc-reference-dict');
      if (response.ok) {
          const data = await response.json();
          return data.doc_reference_dict;
      } else {
          console.error('Request failed with status:', response.status);
          return null;
      }
  } catch (error) {
      console.error('An error occurred:', error);
      return null;
  }
}

(async () => {
  referenceDict = await fetchReferenceDict();
  searchInput.addEventListener("input", function() {
    const query = searchInput.value;
    debouncedFetchSearchResults(query);
  });
})();