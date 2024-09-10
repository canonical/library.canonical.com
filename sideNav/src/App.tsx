import Sidebar from './components/sidebar/sidebar';
import './App.css'


const App: React.FC = () => {
  console.log('App.tsx');
  return (
    <div className='sidebar'>
      <Sidebar/>
    </div>
  )
}

export default App
