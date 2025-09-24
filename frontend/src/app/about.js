const About = () => {
    return (
      <div className="flex justify-center items-center w-full">
        <div className="flex flex-col md:flex-row items-center md:items-start md:space-x-8 mt-8 pb-8 max-w-3xl">
          {/* Profile picture */}
          <img
            src="/ViktorLundin.jpg"
            alt="Viktor Lundin"
            className="rounded-full w-40 h-40 object-cover shadow-lg"
          />
  
          {/* Info section */}
          <div className="mt-6 md:mt-0 text-center md:text-left">
            <h1 className="text-2xl sm:text-2xl md:text-3xl font-bold">
              Viktor Lundin
            </h1>
            <p className="text-lg sm:text-lg md:text-xl">
              Student, Master in Computer and Information Engineering
            </p>
            <p className="text-lg sm:text-lg md:text-xl">Uppsala, Sweden</p>
  
            <p className="mt-6 text-base sm:text-lg leading-relaxed">
              This project is a personal endeavor by Viktor Lundin, a master's
              student in Computer and Information Engineering at Uppsala
              University. It serves as a platform to showcase his skills and
              interests in web development and software engineering.
            </p>
          </div>
        </div>
      </div>
    );
  };
  
  export default About;
  