// Code for hiding the navbar on scroll
var navbar = document.querySelector("header.md-header");

if (window.screen.width >= 1024 && window.screen.height >= 768) {
  // Resolution is 1024x768 or above
  window.addEventListener('scroll', function(){
    var scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    if(scrollTop !== 10){
        navbar.style.top='-70px';
    }
    else{
        navbar.style.top='0';
    }
  });
}
