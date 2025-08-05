import React, { useState } from 'react';
import '../Styles/home.css';
import Navbar from './Navbar';

// @ts-ignore
import coloredbackground from '../Assets/homepage/backendground.png';
// @ts-ignore
import group from '../Assets/homepage/groupimage.png';

const Home = () => {
  return (
    <div>
      <Navbar />
      <div className='home-main-page-div'>
        <div className='home-first-in-page-div'>
          <div className='home-text-div-position'>
            <h1 className='home-h1-main-text'>Affordable Position <span className='colored-span'>Tracking</span> For <span className='colored-span'>Startups</span> And <span className='colored-span'>Businesses</span></h1>
            <div className='home-div-p-text'>
              <p>Affordable SEO tracking for startups: Monitor keyword rankings, get actionable insights, and optimize your content effortlessly.</p>
            </div>
            <button className='home-button-get-started'>Get Started Now</button>
          </div>
          <div>
            <img className='home-word-volume-png' src={group} alt="word group" />
          </div>
        </div>
        <img className='home-colored-background' src={coloredbackground} alt="coloredbackground" />
      </div>
    </div>
  );
};

export default Home;
