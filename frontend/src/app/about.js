const About = () => {
    return (
      <div className="flex justify-center items-center w-full">
        <div className="flex flex-col md:flex-row items-center md:items-start md:space-x-8 mt-8 pb-8 max-w-3xl">
          {/* Profile picture */}
          <img
            src="https://vilu9169.github.io/PhotoPort-V2.0/ViktorLundin.jpg"
            alt="Viktor Lundin"
            className="rounded-full w-40 h-40 object-cover shadow-lg"
          />

          {/* Info section */}
          <div className="mt-6 md:mt-0 text-center md:text-left">
            <h1 className="text-2xl sm:text-2xl md:text-3xl font-bold">
              Viktor Lundin
            </h1>
            <p className="text-lg sm:text-lg md:text-xl">
              M.Sc in Computer and Information Engineering
            </p>
            <p className="text-lg sm:text-lg md:text-xl">Stockholm, Sweden</p>
  
            <p className="mt-6 text-base sm:text-lg leading-relaxed">
              Sometimes I photograph my cat, sometimes I photograph something else.
            </p>
          </div>
        </div>
      </div>
    );
  };

  export default About;
