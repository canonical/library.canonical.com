# Library React Component Project

This react project was created to generate a side navigation component using 
[React + Vite](https://vitejs.dev/guide/) to manage the complex state management. 

## Expected Functionality
Currently there are 3 expected functionalities that the side navigation should have:
#### 1. Infinite level navigation 
This features lets the navigation have infinite levels, in case of wanting to display more than 6, when the next level appear, the first level show will hide, and be accessible by clicking on the **...** element at the top.
#### 2. Soft Roots
Folders which have an **!** in the name will be identify as soft root. This means when that folder is selected the rest of the navigation will hide so that the user can only focus on that specific folder. The breadcrumbs towards that folder will be accessible by click the **...** at the top of the displayed folder
#### 3. Display hidden Folder
In the case the selected folder is hidden by the user as he search for other folders in the navigation. The name of the hidden folder will appear under his parent folder in the following format **(name)** so that the user can easily identify and navigate back.
## Data Expected

The component expects the navigation information is a object tree. The first level should contain the main folder in the Goggle Drive in a set of **name** as the key and **document information** as the object. 
Example:
``` code
{
	"canonical-company-laptops": { object },
	"index": { object },
	"sales-documentation": { object },
	"the-library": { object }.
}
```

Each of the objects should have the following values:
``` code
 "document_name": {
    "active": boolean,
    "breadcrumbs": {"name": string, "path": string,}[]
    "children": { object },
    "expanded": boolean,
    "full_path": string,
    "id": string,
    "mimeType": stirng ("folder" | "document"),
    "name": string,
    "parents": string[],
    "position": integer | null,
    "slug": string,
  }
```

**Note**: The children should contain the same values, each added as a __<Name, Object>__ pair in the children object.  

## Run and Add latest changes to the library
To Run the component Locally and develop or modify functionalities use the following command
``` code 
npm run dev
```
Once the functionalities are done and the component needs to be added to the Library template
First: build the component
``` code
npm run build
```
Second: After build is finish copy both the index-[hash].js and the index-[hash].css in the 
``./dist`` folder locally and copy them to the [./static](https://github.com/canonical/library.canonical.com/tree/main/static) Folder in both the ``/js`` and ``css`` folder respectively.

Third: Make sure to modify both ``base_layout.htlm`` and ``./_partial/_side-navigation.html`` with the reference to the files you just copied

```js
// eslint.config.js
import react from 'eslint-plugin-react'

export default tseslint.config({
  // Set the react version
  settings: { react: { version: '18.3' } },
  plugins: {
    // Add the react plugin
    react,
  },
  rules: {
    // other rules...
    // Enable its recommended rules
    ...react.configs.recommended.rules,
    ...react.configs['jsx-runtime'].rules,
  },
})
```
