import numpy, logging, bilby
from .. import utils
from .. import conversion

logging.basicConfig(level = logging.INFO,
                    format = '%(asctime)s %(message)s',
                    datefmt = '%Y-%m-%d %H:%M:%S')


def notch_filter(val, parameters):
    return 1. - parameters['A'] / ((1 + (parameters['gamma_low']/val) ** parameters['eta_low']) * 
                          (1 + (val/parameters['gamma_high']) ** parameters['eta_high']))

def low_pass_filter(val, parameters):
    return 1./(1 + (val / parameters['mmax']) ** parameters['n'])

choices = ['PowerLaw+Peak', 'MultiPeak', 'BrokenPowerLaw', 'UniformSecondary', 
           'DoubleGaussian', 'LogNormal', 'PowerLawDipBreak', 'PowerLaw']
class Mass:
    def __init__(self, 
                 mass_model, 
                 number_of_samples,
                 parameters = {'alpha':3.37, 'beta': 0.76, 'delta_m':5.23, 
                               'mmin':4.89, 'mmax':88.81, 'lam':0.04, 'mpp': 33.60, 
                               'sigpp':4.59}):
        '''
        Parameters:
        ----------
        mass_model : str 
            The parameterized mass model. [Options: {}]
        number_of_samples : (int)
            The number of samples to generate. [Ideal: Exactly same as redshift samples]
        parameters: (dict, optional)
            A dictionary of model parameters. Default is provided assuming PowerLawPeak
        '''.format(choices)
        self.mass_model = utils.remove_special_characters(mass_model.lower())
        self.number_of_samples = number_of_samples
        self.parameters = parameters

    def sample(self):
        '''
        Generate mass distribution samples based on the chosen parameterised model and its parameters.

        Returns:
        --------
            dict: A dictionary containing source frame mass distribution samples.
        '''
        samples = {}
        try: # Implemented GWPopulation Models
            if 'powerlawpeak' in self.mass_model:
                from gwpopulation.models.mass import SinglePeakSmoothedMassDistribution
                model = SinglePeakSmoothedMassDistribution(normalization_shape=(1000, 1000))
            elif 'multipeak' in self.mass_model:
                from gwpopulation.models.mass import MultiPeakSmoothedMassDistribution
                model = MultiPeakSmoothedMassDistribution(normalization_shape=(1000, 1000))
            elif 'brokenpowerlaw' in self.mass_model:
                from gwpopulation.models.mass import BrokenPowerLawSmoothedMassDistribution
                model = BrokenPowerLawSmoothedMassDistribution(normalization_shape=(1000, 1000))
                
            mass1, mass_ratio = model.m1s, model.qs
            
            # Create dictionaries for supported parameters
            mass_parameters = {param: self.parameters[param] for param in self.parameters if param not in ('beta')}
            mass_ratio_parameters = {param:self.parameters[param] for param in self.parameters if param in ('beta', 'mmin', 'delta_m')}
            
            prob_mass_1 = model.p_m1({'mass_1': mass1}, **mass_parameters)
            prob_mass_ratio = model.p_q({'mass_ratio': mass_ratio, 'mass_1' : mass1}, **mass_ratio_parameters)
            
            primary_mass_prior = bilby.core.prior.Interped(mass1, prob_mass_1, 
                                                           minimum=numpy.min(mass1), 
                                                           maximum=numpy.max(mass1), 
                                                           name='mass_1_source')
            
            mass_ratio_prior = bilby.core.prior.Interped(mass_ratio, prob_mass_ratio, 
                                                         minimum=numpy.min(mass_ratio), 
                                                         maximum=numpy.max(mass_ratio), 
                                                         name='mass_ratio')
            
            samples['mass_1_source'] = primary_mass_prior.sample(self.number_of_samples)
            samples['mass_ratio'] = mass_ratio_prior.sample(self.number_of_samples)
                
        except:
            logging.warn('Parameterised mass model does not exist in gwpopulation')
            logging.info('Generating samples using {} model'.format(self.mass_model))
            if 'uniformsecondary' in self.mass_model:
                from gwpopulation.models.mass import SinglePeakSmoothedMassDistribution
                model = SinglePeakSmoothedMassDistribution(normalization_shape=(1000, 1000))
                mass_parameters = {param: self.parameters[param] for param in self.parameters if param not in ('beta', 'minimum_secondary_mass', 'maximum_secondary_mass')}
                mass1 = model.m1s
                prob_mass_1 = model.p_m1({'mass_1': mass1}, **mass_parameters)
                primary_mass_prior = bilby.core.prior.Interped(mass1, prob_mass_1, 
                                                           minimum=numpy.min(mass1), 
                                                           maximum=numpy.max(mass1), 
                                                           name='mass_1_source')
                samples['mass_1_source'] = primary_mass_prior.sample(self.number_of_samples)
                secondar_mass_prior = bilby.core.prior.analytical.Uniform(minimum=self.parameters['minimum_secondary_mass'],
                                                                          maximum=self.parameters['maximum_secondary_mass'],
                                                                          name='mass_2_source')
                samples['mass_2_source'] = secondar_mass_prior.sample(self.number_of_samples)
            
            elif 'doublegaussian' in self.mass_model:
                '''
                Consider checking https://arxiv.org/pdf/2005.00032.pdf 
                '''
                mass = numpy.linspace(self.parameters['mmin'], self.parameters['mmax'], 5001)
                prior_1 = bilby.core.prior.analytical.TruncatedGaussian(mu=self.parameters['mu_1'], 
                                                                        sigma=self.parameters['sigma_1'], 
                                                                        minimum=self.parameters['mmin'], 
                                                                        maximum=self.parameters['mmax'])
                prob_1 = prior_1.prob(mass) * self.parameters['breaking_fraction']
                prior_2 = bilby.core.prior.analytical.TruncatedGaussian(mu=self.parameters['mu_2'], 
                                                                        sigma=self.parameters['sigma_2'], 
                                                                        minimum=self.parameters['mmin'], 
                                                                        maximum=self.parameters['mmax'])
                prob_2 = prior_2.prob(mass) * (1- self.parameters['breaking_fraction'])
                prob = prob_1 + prob_2
                mass_prior = bilby.core.prior.Interped(mass, prob, 
                                                       minimum=numpy.min(mass), 
                                                        maximum=numpy.max(mass))
                samples['mass_1_source'] = mass_prior.sample(self.number_of_samples)
                samples['mass_2_source'] = mass_prior.sample(self.number_of_samples)
            
            elif 'lognormal' in self.mass_model or 'loggaussian' in self.mass_model:
                mass_prior = bilby.core.prior.analytical.LogNormal(mu=self.parameters['mu'], sigma=self.parameters['sigma'])
                samples['mass_1_source'] = mass_prior.sample(self.number_of_samples)
                samples['mass_2_source'] = mass_prior.sample(self.number_of_samples)
            
            elif 'dip' in self.mass_model:
                '''
                Consider checking Eq.1 of https://arxiv.org/pdf/2111.03498.pdf
                '''
                mass = numpy.linspace(self.parameters['mmin'], self.parameters['mmax'], 5001)
                prob = numpy.zeros_like(mass)
                prior_1 = bilby.core.prior.analytical.PowerLaw(
                    alpha=self.parameters['alpha_1'],
                    minimum=self.parameters['mmin'],
                    maximum=self.parameters['gamma_high']
                )
                prob_1 = prior_1.prob(mass[mass <= self.parameters['gamma_high']])
                prob[mass <= self.parameters['gamma_high']] = (
                    prob_1 * notch_filter(val=mass[mass <= self.parameters['gamma_high']], parameters=self.parameters) *
                    low_pass_filter(val=mass[mass <= self.parameters['gamma_high']], parameters=self.parameters)
                )
            
                prior_2 = bilby.core.prior.analytical.PowerLaw(
                    alpha=self.parameters['alpha_2'],
                    minimum=self.parameters['mmin'],
                    maximum=self.parameters['gamma_high']
                )
                prob_2 = prior_2.prob(mass[mass > self.parameters['gamma_high']])
                prob[mass > self.parameters['gamma_high']] = (
                    prob_2 * notch_filter(val=mass[mass > self.parameters['gamma_high']], parameters=self.parameters) *
                    low_pass_filter(val=mass[mass > self.parameters['gamma_high']], parameters=self.parameters)
                )
                prior = bilby.core.prior.Interped(mass, prob, minimum=numpy.min(mass), maximum=numpy.max(mass))
            
                samples['mass_1_source'] = prior.sample(self.number_of_samples)
                samples['mass_2_source'] = prior.sample(self.number_of_samples)
            elif 'powerlaw' in self.mass_model:
                mass_prior = bilby.core.prior.analytical.PowerLaw(alpha=self.parameters['alpha'],
                                                                  minimum=self.parameters['mmin'],
                                                                  maximum=self.parameters['mmax'])
                
                samples['mass_1_source'] = mass_prior.sample(self.number_of_samples)
                samples['mass_2_source'] = mass_prior.sample(self.number_of_samples)
            elif 'fixed' in self.mass_model:
                samples['mass_1_source'] = numpy.ones(self.number_of_samples) * self.parameters['primary_mass']
                samples['mass_2_source'] = samples['mass_1_source'] * (self.parameters['mass_ratio'] if self.parameters['mass_ratio'] < 1 else 1 / self.parameters['mass_ratio'])
            else:
                raise ValueError('{} is not implemented in gwpopulation. Please choose from {}'.format(self.mass_model, choices))
        
        # Generate all source frame mass parameters from samples
        samples = conversion.generate_mass_parameters(samples, source=True)
        return samples