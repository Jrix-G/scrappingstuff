import React from 'react'
import '../Styles/navbar.css'
// @ts-ignore
import Tandorlogo from '../Assets/logos/project.png';

const Navbar = () => {
  return (
    <div>
      <div className='main-nav'>
          <div className='home-div-logo'>
            <img src={Tandorlogo} alt="Tandor logo" className='tandor-logo' />
            <h1 className='home-div-logo-h1'>Tandor</h1>
          </div>
          <div className='home-center-div-nav'>
            <div className="dropdown">
              <button className="btn btn-secondary dropdown-toggle dropdown-button-perso" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                Products
              </button>
              <ul className="dropdown-menu">
                <li><a className="dropdown-item" href="/homeby">Action</a></li>
                <li><a className="dropdown-item" href="#">Another action</a></li>
                <li><a className="dropdown-item" href="#">Something else here</a></li>
              </ul>
            </div>
            <div className="dropdown">
              <button className="btn btn-secondary dropdown-toggle dropdown-button-perso" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                Services
              </button>
              <ul className="dropdown-menu">
                <li><a className="dropdown-item" href="#">Action</a></li>
                <li><a className="dropdown-item" href="#">Another action</a></li>
                <li><a className="dropdown-item" href="#">Something else here</a></li>
              </ul>
            </div>
            <a href="/home" className='home-center-div-nav-link'>Pricing</a>
            <a href="/home" className='home-center-div-nav-link'>Support</a>
          </div>
          <div className='home-right-login'>
            <div>
              <h1 className='home-login-h1'><a href="/login">Login</a></h1>
            </div>
            <div className='home-sign-up-div'>
              <a href="/signup"><h1>Sign Up</h1></a>
            </div>
          </div>
      </div>
    </div>
  )
}

export default Navbar;